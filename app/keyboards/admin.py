from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Платежи"), KeyboardButton(text="Участники")],
            [KeyboardButton(text="Рейтинг")],
        ],
        resize_keyboard=True,
    )


def payment_decision_keyboard(payment_request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=f"payment:confirm:{payment_request_id}",
                ),
                InlineKeyboardButton(
                    text="Отклонить",
                    callback_data=f"payment:reject:{payment_request_id}",
                ),
            ]
        ]
    )
