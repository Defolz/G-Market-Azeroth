REALM_TYPE_LABELS = {
    "off": "Офф",
    "pirate": "Пиратка",
}

REQUEST_STATUS_LABELS = {
    "new": "Новая",
    "in_progress": "В работе",
    "completed": "Закрыта",
    "cancelled": "Отменена",
}

SUPPORT_STATUS_LABELS = {
    "new": "Новый",
    "answered": "Отвечен",
    "closed": "Закрыт",
}


def realm_type_label(realm_type: str) -> str:
    return REALM_TYPE_LABELS.get(realm_type, realm_type)


def request_status_label(status: str) -> str:
    return REQUEST_STATUS_LABELS.get(status, status)


def support_status_label(status: str) -> str:
    return SUPPORT_STATUS_LABELS.get(status, status)


def is_valid_realm_type(realm_type: str) -> bool:
    return realm_type in REALM_TYPE_LABELS


def is_valid_request_status(status: str) -> bool:
    return status in REQUEST_STATUS_LABELS
