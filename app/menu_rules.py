"""Dependency-free final menu identities shared by HTTP and desktop forms."""
def menu_key(value):
    return ''.join(c for c in value.casefold() if c.isalnum())


OSH_ADDONS = {'tuxum', 'bedanatuxum', 'qazi', 'gosht', 'tuxum1', 'tuxum2'}
PIECE_DRINKS = {'kompot', 'ayron', 'ayran'}
