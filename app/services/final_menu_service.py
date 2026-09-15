"""Add missing final-menu records without guessing or overwriting prices."""
from sqlalchemy import select, text
from app.menu_rules import menu_key
from app.models import Category, Product, AddOn, ProductAddOn, UnitType


def prepare_final_menu(session):
    session.execute(text('SELECT pg_advisory_xact_lock(7010, 1)'))
    categories = list(session.scalars(select(Category)))
    products = list(session.scalars(select(Product)))
    addons = list(session.scalars(select(AddOn)))
    created = 0
    groups = [
        ('Milliy taomlar', [('Osh', 'PORTION'), ('Sho‘rva', 'PORTION'), ('Ko‘za sho‘rva', 'PORTION'),
                           ('Mastava', 'PORTION'), ('Manti', 'PIECE'), ('Jizz', 'AMOUNT')]),
        ('Salatlar', []), ('Nonlar', []), ('Choy va novot', [('Choy', 'PIECE'), ('Novot', 'PIECE')]),
        ('Kompot va ayron', [('Kompot', 'PIECE'), ('Ayron', 'PIECE')]), ('Salqin ichimliklar', []),
    ]
    for position, (title, definitions) in enumerate(groups):
        aliases = {menu_key(title)}
        if title == 'Nonlar':
            aliases.add('non')
        if title == 'Salqin ichimliklar':
            aliases.add('ichimliklar')
        category = next((c for c in categories if menu_key(c.name) in aliases), None)
        if category is None:
            category = Category(name=title, sort_order=position, is_active=True)
            session.add(category)
            session.flush()
            categories.append(category)
            created += 1
        category.name = title
        for name, unit in definitions:
            aliases = {menu_key(name)} | ({'ayran'} if name == 'Ayron' else set())
            product = next((p for p in products if menu_key(p.name) in aliases), None)
            if product is None:
                product = Product(name=name, category_id=category.id, unit_type=UnitType(unit),
                                  base_price=0, allows_manual_price=unit == 'AMOUNT', is_active=True)
                session.add(product)
                session.flush()
                products.append(product)
                created += 1
            else:
                product.category_id = category.id
    osh = next(p for p in products if menu_key(p.name) == 'osh')
    final_addon_ids = []
    for name in ['Tuxum', 'Bedana tuxum', 'Qazi', 'Go‘sht']:
        aliases = {menu_key(name)} | ({'tuxum1'} if name == 'Tuxum' else set())
        addon = next((a for a in addons if menu_key(a.name) in aliases), None)
        if addon is None:
            manual = menu_key(name) == 'gosht'
            addon = AddOn(name=name, unit_type=UnitType.AMOUNT if manual else UnitType.PIECE,
                          base_price=0, allows_manual_price=manual, is_active=True)
            session.add(addon)
            session.flush()
            addons.append(addon)
            created += 1
        addon.name = name
        final_addon_ids.append(addon.id)
        if not session.scalar(select(ProductAddOn).where(ProductAddOn.product_id == osh.id, ProductAddOn.addon_id == addon.id)):
            session.add(ProductAddOn(product_id=osh.id, addon_id=addon.id, is_active=True, is_required=False))
    for link in session.scalars(select(ProductAddOn).where(ProductAddOn.product_id == osh.id)):
        if link.addon_id not in final_addon_ids:
            link.is_active = False
    session.flush()
    return {'created': created, 'message': 'Mavjud narxlar saqlandi. Yangi narxlarni va ichimlik dona narxlarini Admin sozlasin.'}
