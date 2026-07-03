SEGMENTS = ["Restaurante", "Pizzaria", "Lanchonete", "Cafeteria", "Bar", "Fast Food", "Outros"]

PRODUCT_CATEGORIES = ["Pizzas", "Hamburgueres", "Bebidas", "Porcoes", "Sobremesas", "Combos", "Massas", "Saladas", "Cafeteria", "Adicionais"]

PRODUCT_IMAGE_FALLBACKS = {
    "Pizzas": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=900&q=80",
    "Hamburgueres": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=80",
    "Bebidas": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?auto=format&fit=crop&w=900&q=80",
    "Porcoes": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=900&q=80",
    "Sobremesas": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=900&q=80",
    "Combos": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=900&q=80",
    "Massas": "https://images.unsplash.com/photo-1621996346565-e3dbc646d9a9?auto=format&fit=crop&w=900&q=80",
    "Saladas": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=80",
    "Cafeteria": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=900&q=80",
    "default": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=900&q=80",
}


def product_demo_image(product):
    name = (product.get("name") or "").lower()
    if "suco" in name:
        return "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?auto=format&fit=crop&w=900&q=80"
    if "caf" in name:
        return PRODUCT_IMAGE_FALLBACKS["Cafeteria"]
    return PRODUCT_IMAGE_FALLBACKS.get(product.get("category"), PRODUCT_IMAGE_FALLBACKS["default"])


def products_with_demo_images(products):
    items = [dict(product) for product in products]
    for product in items:
        product["image_url"] = product.get("image_url") or product_demo_image(product)
    return items

ORDER_STATUSES = ["Novo", "Em preparo", "Pronto", "Entregue", "Cancelado"]

TABLE_STATUSES = [
    "Livre",
    "Ocupada",
    "Reservada",
    "Conta solicitada",
    "Aguardando limpeza",
    "Pedido em preparo",
]

PAYMENT_METHODS = ["Dinheiro", "Cartao", "Pix", "Outros"]

PERMISSIONS = ["Administrador", "Caixa", "Garcom", "Cozinha", "Gerente"]
