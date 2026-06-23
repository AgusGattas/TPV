"""Formato de ticket en texto plano para impresoras térmicas 80mm (~32 columnas)."""

from decimal import Decimal


# 32 columnas: evita que la impresora parta P.u. / Total en dos líneas
TICKET_WIDTH = 32


def _money(value) -> str:
    amount = int(Decimal(value))
    return f"${amount:,}".replace(",", ".")


def _wrap(text: str, width: int) -> list[str]:
    words = str(text).split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _center(text: str, width: int = TICKET_WIDTH) -> str:
    text = str(text).strip()
    if len(text) >= width:
        return text[:width]
    padding = (width - len(text)) // 2
    return f"{' ' * padding}{text}"


def _line(label: str, amount: str, width: int = TICKET_WIDTH) -> str:
    gap = width - len(label) - len(amount)
    if gap < 1:
        return f"{label[: width - len(amount) - 1]} {amount}"
    return f"{label}{' ' * gap}{amount}"


def _item_numbers_line(quantity, unit_price, total, width: int = TICKET_WIDTH) -> str:
    """Cantidad, P.u. y total en una sola línea (siempre cabe en el ancho del papel)."""
    qty_w = 4
    unit_w = 9
    total_w = 9
    qty_s = f"{quantity:>{qty_w}}"
    unit_s = f"{_money(unit_price):>{unit_w}}"
    total_s = f"{_money(total):>{total_w}}"
    block = f"{qty_s}{unit_s}{total_s}"
    pad = width - len(block)
    if pad < 0:
        return block[-width:]
    return f"{' ' * pad}{block}"


def format_sale_ticket_text(sale, width: int = TICKET_WIDTH) -> str:
    lines: list[str] = []
    separator = "-" * width
    double_sep = "=" * width
    qty_w = 4
    unit_w = 9
    total_w = 9
    numbers_header_pad = width - qty_w - unit_w - total_w

    seller = sale.user.get_full_name() or sale.user.username
    cashier = sale.cashbox.user.get_full_name() or sale.cashbox.user.username

    lines.extend(
        [
            _center("TodoBrilla", width),
            _center("Ticket de venta", width),
            "",
            f"#{sale.ticket_number}",
            sale.created_at.strftime("%d/%m/%Y %H:%M"),
            f"Vendedor: {seller}",
            f"Caja: {cashier}",
            f"Pago: {sale.get_payment_method_display()}",
            separator,
            "Producto",
            f"{' ' * numbers_header_pad}{'Cant':>{qty_w}}{'P.u.':>{unit_w}}{'Total':>{total_w}}",
            separator,
        ]
    )

    for item in sale.items.all():
        product_name = item.product.name
        if item.discount_percentage > 0:
            product_name = f"{product_name} (-{item.discount_percentage}%)"

        for name_line in _wrap(product_name, width):
            lines.append(name_line[:width])
        lines.append(_item_numbers_line(item.quantity, item.unit_price, item.total, width))

    lines.extend(
        [
            separator,
            _line("Subtotal", _money(sale.subtotal), width),
        ]
    )

    if sale.total_discount > 0:
        lines.append(_line("Descuentos", f"-{_money(sale.total_discount)[1:]}", width))

    lines.extend(
        [
            double_sep,
            _line("TOTAL", _money(sale.total_final), width),
            double_sep,
        ]
    )

    if sale.notes:
        lines.extend(["", "Notas:", *_wrap(sale.notes, width)])

    lines.extend(["", _center("Gracias por su compra", width), ""])

    return "\n".join(lines)


def format_sale_ticket_escpos(sale, width: int = TICKET_WIDTH) -> bytes:
    """Bytes ESC/POS para impresora térmica (sin PDF ni diálogo del navegador)."""
    text = format_sale_ticket_text(sale, width=width)
    init = b"\x1b\x40"
    select_cp850 = b"\x1b\x74\x02"
    left_align = b"\x1b\x61\x00"
    feed = b"\n\n\n"
    cut = b"\x1d\x56\x00"
    body = text.encode("cp850", errors="replace")
    return init + select_cp850 + left_align + body + feed + cut
