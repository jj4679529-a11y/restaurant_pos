from app.ui.api_client import ApiError, PosApiClient
from app.menu_rules import PIECE_DRINKS


RESOURCES = {
    'categories': '/api/categories', 'products': '/api/products', 'addons': '/api/addons',
    'presets': '/api/manual-price-presets', 'workers': '/api/delivery-workers',
    'users': '/api/users', 'printers': '/api/admin/printers', 'settings': '/api/admin/settings',
}


def menu_name(name):
    return ''.join(c for c in name.casefold() if c.isalnum())


def protect_menu(resource, data, original=None):
    data = dict(data)
    name = menu_name((original or {}).get('name') or data.get('name', ''))
    new_name = menu_name(data.get('name', ''))
    if resource == 'products' and new_name == 'gosht':
        raise ValueError('Go‘sht faqat qo‘shimcha bo‘lishi mumkin')
    if resource == 'products' and new_name in PIECE_DRINKS:
        data.update(unit_type='PIECE', allows_manual_price=False)
    if resource == 'products' and name in {'osh', 'jizz'}:
        if new_name != name:
            raise ValueError('Osh/Jizz nomini bu oynada o‘zgartirmang')
        data.update(allows_manual_price=name == 'jizz', base_price=0,
                    unit_type='PORTION' if name == 'osh' else 'AMOUNT')
    if resource == 'addons':
        if name == 'gosht':
            if new_name != name:
                raise ValueError('Go‘sht nomini bu oynada o‘zgartirmang')
            data.update(allows_manual_price=True, base_price=0, unit_type='AMOUNT')
        elif name.startswith('tuxum') or name == 'qazi':
            data.update(allows_manual_price=False, unit_type='PIECE')
    return data


class AdminApiClient(PosApiClient):
    def list_records(self, resource):
        path = RESOURCES[resource]
        if resource in {'categories', 'addons', 'workers'}:
            path += '?include_inactive=true'
        if resource == 'products':
            return self._all_pages(path + '?is_active=true') + self._all_pages(path + '?is_active=false')
        if resource == 'presets':
            path = '/api/admin/manual-price-presets'
        if resource == 'settings':
            return self.get(path)
        return self._all_pages(path)

    def save_record(self, resource, data, original=None):
        data = protect_menu(resource, data, original)
        path = RESOURCES[resource]
        if original:
            key = original['key'] if resource == 'settings' else original['id']
            path += f'/{key}'
            method = 'PUT' if resource == 'printers' else 'PATCH'
        else:
            method = 'POST'
        return self.request(method, path, data)

    def save_osh_prices(self, product_id, half_price, full_price):
        return self.request('PUT', f'/api/admin/products/{product_id}/osh-prices',
                            {'half_price': half_price, 'full_price': full_price})

    def save_price_options(self, product_id, options):
        existing = self._all_pages(
            f'/api/products/{product_id}/price-options'
        )

        used_ids = set()
        saved = []

        for option in options:
            match = next(
                (
                    row for row in existing
                    if row.get('name') == option['name']
                ),
                None,
            )

            payload = {
                'name': option['name'],
                'quantity': str(option['quantity']),
                'price': int(option['price']),
                'is_active': True,
            }

            if match:
                record = self.request(
                    'PATCH',
                    f"/api/price-options/{match['id']}",
                    payload,
                )
                used_ids.add(match['id'])
            else:
                record = self.request(
                    'POST',
                    f'/api/products/{product_id}/price-options',
                    payload,
                )
                used_ids.add(record['id'])

            saved.append(record)

        for old in existing:
            if old['id'] not in used_ids and old.get('is_active', True):
                self.request(
                    'PATCH',
                    f"/api/price-options/{old['id']}",
                    {'is_active': False},
                )

        return saved

    def upload_image(self, data):
        if len(data) > 5 * 1024 * 1024:
            raise ValueError('Rasm hajmi 5 MB dan oshmasin')
        return self.request('POST', '/api/admin/product-images', raw_body=data)['image_path']

    def links(self, product_id):
        return self.get(f'/api/admin/products/{product_id}/addons')

    def set_link(self, product_id, addon_id, active, required=False):
        return self.request('PUT', f'/api/admin/products/{product_id}/addons/{addon_id}',
                            {'is_active': active, 'is_required': required})
