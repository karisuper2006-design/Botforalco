import os
import random
from pathlib import Path
from typing import Optional, Union

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, TimedOut
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Import our new modules
import database
import cocktails_data as data

# --- Configuration ---
# Задайте токен и путь к обложке при необходимости.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
COCKTAIL_IMAGE_PATH = Path("cocktail.jpg")
# Все видео храним в папке video рядом с этим файлом
VIDEOS_DIR = Path(__file__).parent / "video"

NAME_TO_SLUG: dict[str, str] = {}


def _normalize_name(text: str) -> str:
    return text.strip().lower()


def _register_name(name: str, slug: str) -> None:
    if not name:
        return
    NAME_TO_SLUG.setdefault(_normalize_name(name), slug)


def build_name_index() -> None:
    """Строит индекс имен/синонимов коктейлей для поиска по вводу."""
    NAME_TO_SLUG.clear()
    for slug, label in data.ALCOHOLIC_COCKTAILS + data.NON_ALCOHOLIC_COCKTAILS:
        _register_name(label, slug)
        _register_name(slug.replace("_", " "), slug)
    for slug, details in data.COCKTAIL_DETAILS.items():
        _register_name(details.get("title", ""), slug)
    # Быстрые клавиатурные варианты
    _register_name("1", " ")


def find_cocktail_slug(user_input: str) -> Optional[str]:
    """Ищет слаг по названию."""
    if not user_input:
        return None
    if not NAME_TO_SLUG:
        build_name_index()
    return NAME_TO_SLUG.get(_normalize_name(user_input))


def search_by_ingredient(query: str) -> list[tuple[str, str]]:
    """Ищет коктейли, содержащие ингредиент. Возвращает список (slug, title)."""
    query = query.lower()
    results = []
    for slug, details in data.COCKTAIL_DETAILS.items():
        ingredients = details.get("ingredients", [])
        # Проверяем каждый ингредиент
        for ing in ingredients:
            if query in ing.lower():
                results.append((slug, details["title"]))
                break
    return results


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствует пользователя и показывает первую клавиатуру."""
    if update.message is None:
        return
    await send_main_menu(update.message)


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые ответы пользователя."""
    if not update.message:
        return

    answer = (update.message.text or "").lower()
    user_id = update.effective_user.id if update.effective_user else None

    # Обработка команд меню
    if "избран" in answer:
        await send_favorites_list(message=update.message, user_id=user_id)
        return
    
    if "повезёт" in answer or "random" in answer:
        # Случайный коктейль
        if not data.ALL_SLUGS:
            await update.message.reply_text("База коктейлей пуста.")
            return
        slug = random.choice(list(data.ALL_SLUGS))
        if slug in data.COCKTAIL_DETAILS:
             await send_cocktail_message(update.message, slug, data.COCKTAIL_DETAILS[slug], user_id)
        return

    if answer.startswith("2") or "безалког" in answer:
        await send_nonalcohol_inline_keyboard(update.message)
        return
    
    if answer.startswith("1") or "алкоголь" in answer:
        await send_alcohol_inline_keyboard(update.message)
        return

    # 1. Попытка найти по точному названию
    slug = find_cocktail_slug(answer)
    if slug and slug in data.COCKTAIL_DETAILS:
        await send_cocktail_message(update.message, slug, data.COCKTAIL_DETAILS[slug], user_id)
        return

    # 2. Попытка найти по ингредиентам
    found = search_by_ingredient(answer)
    if found:
        if len(found) == 1:
            # Нашли ровно один — показываем
            slug, _ = found[0]
            await send_cocktail_message(update.message, slug, data.COCKTAIL_DETAILS[slug], user_id)
        else:
            # Нашли несколько — предлагаем выбор
            buttons = [
                InlineKeyboardButton(text=title, callback_data=f"{data.ALCOHOL_PREFIX}:{slug}") 
                for slug, title in found[:10] # Ограничим до 10 для красоты
            ]
            keyboard = InlineKeyboardMarkup.from_column(buttons)
            await update.message.reply_text(f"Нашел несколько коктейлей с «{answer}»:", reply_markup=keyboard)
    else:
        await update.message.reply_text(
            "Не нашёл коктейль ни по названию, ни по ингредиентам. \n"
            "Попробуйте нажать кнопки меню или ввести другое название (например, 'Негрони' или 'вермут')."
        )


async def send_main_menu(message: Message | None) -> None:
    """Показывает основное меню выбора типа коктейлей."""
    if not message:
        return

    text = "Какой коктейль сегодня хотите?"
    keyboard = ReplyKeyboardMarkup(data.CHOICES, one_time_keyboard=True, resize_keyboard=True)

    if COCKTAIL_IMAGE_PATH.exists():
        try:
            with COCKTAIL_IMAGE_PATH.open("rb") as image_file:
                await message.reply_photo(photo=image_file, caption=text, reply_markup=keyboard)
        except TimedOut:
            await message.reply_text(text, reply_markup=keyboard)
    else:
        await message.reply_text(text, reply_markup=keyboard)


async def edit_query_with_text_or_photo(
    query: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup,
    parse_mode: Optional[str] = None,
) -> None:
    """Ставит текст на сообщение по возможности; иначе заменяет медиа на фото."""
    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        return
    except BadRequest:
        pass

    if COCKTAIL_IMAGE_PATH.exists():
        with COCKTAIL_IMAGE_PATH.open("rb") as image_file:
            await query.edit_message_media(
                media=InputMediaPhoto(image_file, caption=text, parse_mode=parse_mode),
                reply_markup=keyboard,
            )
    else:
        try:
            await query.message.delete()
        except BadRequest:
            pass
        await query.message.chat.send_message(text, reply_markup=keyboard, parse_mode=parse_mode)


async def send_alcohol_inline_keyboard(message: Message | None = None, query: CallbackQuery | None = None) -> None:
    """Отправляет или обновляет инлайн-клавиатуру с коктейлями."""
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"{data.ALCOHOL_PREFIX}:{slug}")
        for slug, label in data.ALCOHOLIC_COCKTAILS
    ]
    buttons.append(InlineKeyboardButton("← Назад", callback_data=data.MENU_BACK_CALLBACK))
    keyboard = InlineKeyboardMarkup.from_column(buttons)
    if query:
        await edit_query_with_text_or_photo(query, "Выберите коктейль:", keyboard)
    elif message:
        await message.reply_text("Выберите коктейль:", reply_markup=keyboard)


async def send_nonalcohol_inline_keyboard(message: Message | None = None, query: CallbackQuery | None = None) -> None:
    """Отправляет или обновляет инлайн-клавиатуру безалкогольных коктейлей."""
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"{data.NON_ALCOHOL_PREFIX}:{slug}")
        for slug, label in data.NON_ALCOHOLIC_COCKTAILS
    ]
    buttons.append(InlineKeyboardButton("← Назад", callback_data=data.MENU_BACK_CALLBACK))
    keyboard = InlineKeyboardMarkup.from_column(buttons)
    if query:
        await edit_query_with_text_or_photo(query, "Выберите безалкогольный коктейль:", keyboard)
    elif message:
        await message.reply_text("Выберите безалкогольный коктейль:", reply_markup=keyboard)


async def send_favorites_list(
    message: Message | None = None,
    query: CallbackQuery | None = None,
    user_id: Optional[int] = None,
) -> None:
    """Показывает избранные коктейли списком кнопок."""
    if user_id is None:
         # Should not happen typically
         return

    # Get favorites from DB
    user_favs = database.get_user_favorites(user_id)
    favorites = [
        slug for slug in user_favs if slug in data.COCKTAIL_DETAILS
    ]
    
    buttons = [
        InlineKeyboardButton(data.COCKTAIL_DETAILS[slug]["title"], callback_data=f"{data.FAV_LIST_PREFIX}:{slug}")
        for slug in favorites
    ]
    buttons.append(InlineKeyboardButton("← Назад", callback_data=data.MENU_BACK_CALLBACK))
    keyboard = InlineKeyboardMarkup.from_column(buttons)

    text = "Избранные коктейли:" if favorites else "Избранных коктейлей пока нет."
    if query:
        await edit_query_with_text_or_photo(query, text, keyboard)
    elif message:
        await message.reply_text(text, reply_markup=keyboard)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Реагирует на нажатия инлайн-кнопок."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    if ":" not in query.data:
        return

    prefix, slug = query.data.split(":", 1)
    user_id = query.from_user.id if query.from_user else None

    if prefix == "menu" and slug == "back":
        await send_main_menu(query.message)
        return

    if prefix == data.FAV_ADD_PREFIX:
        # Toggle Favorite via DB
        if user_id is not None:
             is_now_fav = database.toggle_favorite(user_id, slug)
             msg = "Добавлено в избранное" if is_now_fav else "Удалено из избранного"
             await query.answer(msg, show_alert=False)
        else:
             is_now_fav = False

        details = data.COCKTAIL_DETAILS.get(slug)
        if not details:
            await query.answer("Мы пока не знаем этот коктейль", show_alert=True)
            return

        # Determine where to go back
        if slug in data.ALCOHOLIC_SLUGS:
            back_callback = data.BACK_CALLBACK_ALC
        elif slug in data.NON_ALCOHOLIC_SLUGS:
            back_callback = data.BACK_CALLBACK_NA
        else:
            back_callback = data.BACK_CALLBACK_FAV
        
        await send_cocktail_response(query, slug, details, back_callback, user_id)
        return

    if prefix == data.FAV_LIST_PREFIX:
        if slug == "back":
            await send_favorites_list(query=query, user_id=user_id)
            return
        details = data.COCKTAIL_DETAILS.get(slug)
        if not details:
            await query.edit_message_text("Мы пока не знаем этот коктейль 😅")
            return
        await send_cocktail_response(query, slug, details, data.BACK_CALLBACK_FAV, user_id)
        return

    if prefix == data.ALCOHOL_PREFIX:
        back_callback = data.BACK_CALLBACK_ALC
    elif prefix == data.NON_ALCOHOL_PREFIX:
        back_callback = data.BACK_CALLBACK_NA
    else:
        return

    if slug == "back":
        if prefix == data.ALCOHOL_PREFIX:
            await send_alcohol_inline_keyboard(query=query)
        else:
            await send_nonalcohol_inline_keyboard(query=query)
        return

    details = data.COCKTAIL_DETAILS.get(slug)
    if not details:
        await query.edit_message_text("Мы пока не знаем этот коктейль 😅")
        return

    await send_cocktail_response(query, slug, details, back_callback, user_id)


def format_cocktail_details(details: dict) -> str:
    """Собирает красивое описание коктейля."""
    parts = [
        f"🍸 <b>{details['title']}</b>",
        "",
        "<b>Ингредиенты:</b>",
        *[f"• {item}" for item in details["ingredients"]],
        "",
        f"<b>Метод:</b>\n{details['method']}",
    ]
    if details.get("garnish"):
        parts.extend(["", f"<b>Украшение:</b>\n{details['garnish']}"])
    if details.get("note"):
        parts.extend(["", f"<b>Заметка:</b>\n{details['note']}"])

    return "\n".join(parts).strip()


def resolve_video_source(slug: str) -> Optional[Union[str, Path]]:
    """Находит источник видео: локальный файл или URL."""
    value = data.COCKTAIL_VIDEOS.get(slug)
    if value is None:
        return None

    # URL — отдать как есть
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value

    # Локальный файл: ищем в папке /video рядом с проектом (или используем абсолютный путь)
    if isinstance(value, Path):
        candidate = value if value.is_absolute() else VIDEOS_DIR / value
    else:
        candidate = VIDEOS_DIR / str(value)

    return candidate if candidate.exists() else None


async def send_cocktail_response(
    query: CallbackQuery, slug: str, details: dict, back_callback_data: str, user_id: Optional[int]
) -> None:
    """Возвращает рецепт и при наличии заменяет сообщение на видео с тем же содержанием."""
    if not query.message:
        return

    # Check DB
    is_fav = database.is_favorite(user_id, slug) if user_id else False
    fav_text = "✅ В избранном" if is_fav else "⭐ Добавить в избранное"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(fav_text, callback_data=f"{data.FAV_ADD_PREFIX}:{slug}")],
        [InlineKeyboardButton("← Назад", callback_data=back_callback_data)],
    ])
    caption = format_cocktail_details(details)

    # Try cached file_id first for instant delivery
    cached_file_id = database.get_video_file_id(slug)
    if cached_file_id:
        try:
            await query.edit_message_media(
                media=InputMediaVideo(
                    media=cached_file_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                ),
                reply_markup=keyboard,
            )
            return
        except (BadRequest, TimedOut):
            # Cache invalid or timeout, continue to re-upload
            pass

    video_source = resolve_video_source(slug)

    if video_source:
        # Retry logic for timeouts
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if isinstance(video_source, Path):
                    with video_source.open("rb") as file_obj:
                        result = await query.edit_message_media(
                            media=InputMediaVideo(
                                media=file_obj,
                                caption=caption,
                                parse_mode=ParseMode.HTML,
                            ),
                            reply_markup=keyboard,
                        )
                        # Cache the file_id for future instant delivery
                        if result and result.video:
                            database.save_video_file_id(slug, result.video.file_id)
                else:
                    result = await query.edit_message_media(
                        media=InputMediaVideo(
                            media=video_source,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                        ),
                        reply_markup=keyboard,
                    )
                    # Cache the file_id for future instant delivery
                    if result and result.video:
                        database.save_video_file_id(slug, result.video.file_id)
                return  # Success, exit
            except TimedOut:
                if attempt < max_retries:
                    continue  # Retry
                # All retries failed, fallback to text
                await edit_query_with_text_or_photo(query, caption, keyboard, parse_mode=ParseMode.HTML)
                return
    else:
        await edit_query_with_text_or_photo(query, caption, keyboard, parse_mode=ParseMode.HTML)


async def send_cocktail_message(
    message: Message, slug: str, details: dict, user_id: Optional[int]
) -> None:
    """Отправляет рецепт (и видео, если есть) в ответ на текстовый ввод."""
    
    is_fav = database.is_favorite(user_id, slug) if user_id else False
    fav_text = "✅ В избранном" if is_fav else "⭐ Добавить в избранное"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(fav_text, callback_data=f"{data.FAV_ADD_PREFIX}:{slug}")],
        [InlineKeyboardButton("← Назад", callback_data=data.MENU_BACK_CALLBACK)],
    ])
    caption = format_cocktail_details(details)

    # Try cached file_id first for instant delivery
    cached_file_id = database.get_video_file_id(slug)
    if cached_file_id:
        try:
            await message.reply_video(
                video=cached_file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            return
        except (BadRequest, TimedOut):
            # Cache invalid or timeout, continue to re-upload
            pass

    video_source = resolve_video_source(slug)

    if video_source:
        # Retry logic for timeouts
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if isinstance(video_source, Path):
                    with video_source.open("rb") as file_obj:
                        sent = await message.reply_video(
                            video=file_obj,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard
                        )
                        # Cache the file_id for future instant delivery
                        if sent and sent.video:
                            database.save_video_file_id(slug, sent.video.file_id)
                else:
                    sent = await message.reply_video(
                        video=video_source,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
                    # Cache the file_id for future instant delivery
                    if sent and sent.video:
                        database.save_video_file_id(slug, sent.video.file_id)
                return  # Success, exit
            except TimedOut:
                if attempt < max_retries:
                    continue  # Retry
                # All retries failed, fallback to text
                await message.reply_text(
                    text=caption + "\n\n⚠️ Видео временно недоступно",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )
                return
    else:
        await message.reply_text(
            text=caption,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )


def main() -> None:
    """Запускает Telegram-бота и регистрирует обработчики."""
    
    # Init Database
    database.init_db()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(120.0)  # Больше времени для загрузки видео
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("Bot is starting polling...", flush=True)
    app.run_polling()


if __name__ == "__main__":
    main()
