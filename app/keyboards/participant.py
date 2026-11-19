from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


ACCEPT_RULES_CALLBACK = "participant:accept_rules"
PAY_DEBT_CALLBACK = "participant:pay_debt"
PAY_ENTRY_CALLBACK = "participant:pay_entry"


def accept_rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Принимаю правила", callback_data=ACCEPT_RULES_CALLBACK)]
        ]
    )


def pay_debt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить долг", callback_data=PAY_DEBT_CALLBACK)]
        ]
    )


def pay_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить вход", callback_data=PAY_ENTRY_CALLBACK)]
        ]
    )
