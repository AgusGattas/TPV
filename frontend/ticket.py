"""Formato de ticket en texto plano para impresoras térmicas 80mm (~42 columnas)."""

from decimal import Decimal


TICKET_WIDTH = 42


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


def format_sale_ticket_text(sale, width: int = TICKET_WIDTH) -> str:
    lines: list[str] = []
    separator = "-" * width
    double_sep = "=" * width
    name_width = 22
    qty_width = 4
    unit_width = 7
    total_width = 7

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
            f"{'Producto':<{name_width}}{'Cant':>{qty_width}}{'P.u.':>{unit_width}}{'Total':>{total_width}}",
            separator,
        ]
    )

    for item in sale.items.all():
        product_name = item.product.name
        if item.discount_percentage > 0:
            product_name = f"{product_name} (-{item.discount_percentage}%)"

        name_lines = _wrap(product_name, name_width)
        first_line = name_lines[0][:name_width]
        lines.append(
            f"{first_line:<{name_width}}"
            f"{item.quantity:>{qty_width}}"
            f"{_money(item.unit_price):>{unit_width}}"
            f"{_money(item.total):>{total_width}}"
        )
        for extra in name_lines[1:]:
            lines.append(extra[:width])

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
