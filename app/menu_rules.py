"""Restaurant menu identities shared by API and desktop UI."""


def menu_key(value):
    return ''.join(
        c
        for c in (value or '').casefold()
        if c.isalnum()
    )


OSH_ADDONS = {
    'tuxum',
    'bedanatuxum',
    'qazi',
    'gosht',
}


PORTION_PRODUCTS = {
    'osh',
    'shurva',
    'shorva',
    'kozashurva',
    'kozashorva',
    'mastava',
}


PIECE_PRODUCTS = {
    'manti',
}


MANUAL_PRICE_PRODUCTS = {
    'jizz',
}


LITER_CATEGORIES = {
    'kompotvaayron',
    'salqinichimliklar',
}


LITER_CHOICES = (
    '0.5',
    '1',
    '1.5',
    '2',
)


BREAD_CHOICES = (
    'Butun',
    'Yarim',
    'Chorak',
)


# Backward-compatible symbol while old imports are removed.
PIECE_DRINKS = {'kompot', 'ayron', 'ayran'}
