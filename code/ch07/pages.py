"""The Example Supply help pages that Chapter 7 searches.

Twelve policy pages, one archived policy page, and thirty product
pages for the book's invented parts store. Each page is plain text:
a "# " title line, "## " heading lines, and body lines wrapped to
fit the book. Every rule and number here is synthetic; the refund
rules match the Chapter 5 policy.
"""

RETURNS = """\
# Returns and exchanges
## Return window
Most items can be sent back within 30 days of delivery. Ask for a
return number (RMA) on the orders page before you post anything.
Parcels that arrive without an RMA number go back to the sender.
Items must be unused and in the original packaging, with labels on.
## Items that cannot come back
Hose cut to length, opened tins of bearing grease, thread seal tape
with a broken seal, custom-machined parts, and anything marked final
sale cannot be returned. The product page shows a final sale badge
on every item in this group.
## Return postage
The shopper pays return postage unless the store sent the wrong item
or the item arrived damaged. Use a tracked service, because a parcel
that never reaches the warehouse cannot be credited.
## Exchanges
To swap a size or a model, start a return and place a new order.
Exchanges are not held: the new order ships at the price on the day
it is placed.
"""

REFUNDS = """\
# Refunds
## When a refund is paid
Refunds are paid within 5 business days after the warehouse inspects
the returned item. The money goes back to the original payment
method; store credit is offered only when the shopper asks for it.
Only shipped or delivered orders can be refunded.
## What is refunded
A refund covers the item price and tax. Original shipping charges
are not refunded unless the store made the mistake. A refund cannot
exceed the order total.
## Partial refunds and restocking
Items returned without the original packaging, or with signs of use,
get a partial refund with a 15 percent restocking fee. Bearing kits
with a broken seal are refunded at half price.
## Who approves a refund
A person approves every refund before money moves. Each order can
have one open refund request at a time; a second request waits until
the first is closed.
"""

SHIPPING = """\
# Shipping and delivery
## Delivery times
Standard delivery takes 3 to 5 business days inside the country.
Express delivery arrives the next business day when the order is
placed before 2 pm warehouse time. Orders placed on a weekend leave
the warehouse on Monday.
## Shipping charges
Shipping is free on orders over $150 before tax. Smaller orders pay
a flat $9.95 for standard delivery; express costs $24.
## Tracking a parcel
A tracking link is emailed when the label prints. The link can take
up to 24 hours to show the first scan.
## International orders
Example Supply ships to 30 countries. Import duties and taxes are
paid by the recipient on delivery, and international orders cannot
use express delivery.
"""

DAMAGED = """\
# Damaged, missing, or wrong items
## Report within 48 hours
Report a damaged or wrong item within 48 hours of delivery, with
photos of the item, the box, and the shipping label. Reports after
48 hours are handled as warranty claims.
## Wrong item sent
When the store sends the wrong item, the right one ships by express
at no charge and a prepaid label comes for the wrong one.
## Missing items
Large orders can arrive in more than one box. Check the packing slip
for a split shipment note before you report an item as missing.
## Lost parcels
If tracking has not changed for 7 days, the store opens a claim with
the carrier and sends a replacement or a refund, whichever the
shopper prefers.
"""

WARRANTY = """\
# Warranty
## Warranty period
Parts carry a 12 month warranty from delivery against defects in
material and workmanship. Ball valves and pressure gauges carry 24
months.
## What the warranty does not cover
Wear parts such as V-belts, seals, and hose are not covered once
fitted. Damage from wrong fitting, over-tightening, or running past
the rated pressure is not covered either.
## Making a claim
Send the order number, a photo of the fault, and a short note on how
the part was used. A person reviews every claim within 3 business
days and may ask for the part to be sent in.
"""

ORDERS = """\
# Changing or canceling an order
## Canceling an order
An order can be canceled free of charge while its status is
processing. Once it has shipped it cannot be canceled; start a return
after delivery instead.
## Changing the address
The delivery address can be changed until the shipping label prints,
usually within 2 hours of the order. After that, ask the carrier to
redirect the parcel.
## Adding items
Items cannot be added to an order that is already placed. Place a
second order; both ship together if the first has not left the
warehouse.
"""

PAYMENTS = """\
# Payment and invoices
## Ways to pay
Example Supply takes credit and debit cards, bank transfer, and trade
accounts. Bank transfer orders ship after the money arrives, usually
1 to 2 business days.
## Trade accounts
Businesses can apply for a trade account with net 30 terms. Approval
takes up to 5 business days and needs a company registration number.
## Invoices and tax exemption
Every order has a PDF invoice on the orders page. Tax-exempt buyers
upload their exemption certificate before ordering; tax cannot be
removed from an order after it is paid.
## Failed payments
If a card is declined, the order waits 48 hours for a new payment and
is then canceled automatically.
"""

SAFETY = """\
# Hazardous goods
## Aerosols and sprays
Aerosol cans, such as spray grease and contact cleaner, ship by
ground only. They cannot travel by air, so express delivery and
international shipping are not available for them.
## Safety data sheets
A safety data sheet (SDS) for every chemical product, including
bearing grease and thread sealant, can be downloaded from its product
page.
## Restricted places
Some products cannot ship to PO boxes or to a few remote areas; the
checkout page says so before payment.
"""

BULK = """\
# Bulk and trade pricing
## Volume discounts
Orders of 50 or more units of one SKU get 10 percent off. Orders of
200 or more units get 15 percent off. The discount shows in the cart.
## Quotes
For orders over $2,000, ask for a quote. A quote is valid for 30 days
and holds the price, not the stock.
## Samples
Trade accounts can order up to three free samples a month, such as a
single HC-038 hose clamp or one FT-038 fitting, to test fit.
"""

PRIVACY = """\
# Your account and data
## What the store keeps
The store keeps your name, addresses, order history, and support
messages. Card numbers are held by the payment provider, not by
Example Supply.
## Deleting your account
Ask support to delete your account. The account is closed within 30
days, and invoices are kept for 7 years because tax law requires it.
## Email preferences
Every marketing email has an unsubscribe link. Order and shipping
emails cannot be turned off while an order is open.
"""

CARE = """\
# Product care and fitting
## Bearing kits
Pack each BK-6204 bearing with GR-400 grease to about a third of its
free space. Too much grease makes the bearing run hot.
## Hose clamps
Tighten an HC-038 hose clamp to 4 newton meters. Over-tightening cuts
into the hose and voids the warranty.
## Thread seal tape
Wrap TT-012 tape three to four times clockwise, seen from the end of
the thread. Do not use tape on flare or compression fittings.
## Pressure gauges
Check a PG-010 gauge against a known reference once a year. A gauge
that reads off by more than 2 percent should be replaced.
"""

STOCK = """\
# Stock and back orders
## Out of stock items
An item that is out of stock can still be ordered as a back order.
The page shows the expected restock date.
## Back orders
Back-ordered items ship as soon as they arrive. The card is charged
when the item ships, not when the order is placed.
## Restock alerts
Press notify me on the product page to get one email when the item
is back. Alerts expire after 90 days.
## Discontinued items
When a part is discontinued, its page names a replacement part where
one exists.
"""

OLD_RETURNS = """\
# Returns policy (archived, 2024)
## Return window
Until January 2025, items could be sent back within 14 days of
delivery, and a 20 percent restocking fee applied to every return.
## Return postage
Under the old policy the store refunded return postage on every
return. This page is kept for orders placed before 2025.
"""

PRODUCT = """\
# {name}
## About this part
Part number {sku}. {blurb}
## Delivery, returns, and warranty
This part ships from the main warehouse. Delivery times, returns,
refunds, and the warranty follow the store policy pages; read them
before you order.
"""

PRODUCTS = [
    ("HC-038", "Hose clamp, 3/8 in",
     "A stainless worm-drive clamp for hose with a 3/8 in bore."),
    ("HC-100", "Hose clamp, 1 in",
     "A stainless worm-drive clamp for hose with a 1 in bore."),
    ("HC-200", "Hose clamp, 2 in",
     "A heavy stainless clamp for suction hose with a 2 in bore."),
    ("HS-038", "Rubber hose, 3/8 in, per meter",
     "Air and water hose, cut to the length you order."),
    ("BK-6204", "Bearing kit 6204",
     "Two sealed 6204 ball bearings with spacers and seals."),
    ("BK-6205", "Bearing kit 6205",
     "Two sealed 6205 ball bearings for pumps and motors."),
    ("GR-400", "Bearing grease, 400 g",
     "Lithium grease in a 400 g tin for bearings and slides."),
    ("GR-100", "Bearing grease, 100 g tube",
     "The same lithium grease in a tube for a grease gun."),
    ("GR-SPR", "Spray grease, 400 ml",
     "Aerosol chain and gear grease with a straw nozzle."),
    ("CC-400", "Contact cleaner, 400 ml",
     "Aerosol cleaner for switches and contacts; dries fast."),
    ("FT-038", "Brass fitting, 3/8 in",
     "A threaded brass fitting for air and water lines."),
    ("FT-012", "Brass fitting, 1/2 in",
     "A threaded brass fitting for 1/2 in pipe."),
    ("FT-ELB", "Brass elbow, 3/8 in",
     "A 90 degree threaded elbow for tight corners."),
    ("TT-012", "Thread seal tape",
     "PTFE tape, 12 mm wide, for threaded pipe joints."),
    ("TS-050", "Thread sealant paste, 50 ml",
     "Pipe joint paste for water and air; sets in one hour."),
    ("PG-010", "Pressure gauge, 0-10 bar",
     "A dial gauge for air and water lines up to 10 bar."),
    ("PG-016", "Pressure gauge, 0-16 bar",
     "A glycerin-filled gauge for pumps up to 16 bar."),
    ("VB-A42", "V-belt A42",
     "A classic section A belt, 42 in long, for pumps and fans."),
    ("VB-A50", "V-belt A50",
     "A classic section A belt, 50 in long."),
    ("VB-B60", "V-belt B60",
     "A wider section B belt, 60 in long, for compressors."),
    ("CT-100", "Cable ties, pack of 100",
     "Nylon ties, 200 mm long, sold in packs of 100."),
    ("CT-500", "Cable ties, pack of 500",
     "Black nylon ties, 300 mm long, for outdoor use."),
    ("HK-009", "Hex key set, 9 pieces",
     "Nine hex keys from 1.5 to 10 mm in a holder."),
    ("TW-025", "Torque wrench, 5-25 Nm",
     "A click torque wrench for small fasteners and clamps."),
    ("BV-012", "Ball valve, 1/2 in",
     "A quarter-turn brass ball valve with a lever handle."),
    ("BV-034", "Ball valve, 3/4 in",
     "A quarter-turn brass ball valve for 3/4 in pipe."),
    ("CV-012", "Check valve, 1/2 in",
     "A spring check valve that stops water flowing back."),
    ("OR-KIT", "O-ring kit, 225 pieces",
     "Nitrile O-rings in 18 sizes in a sorted box."),
    ("SK-6204", "Seal kit for 6204 bearings",
     "Spare lip seals to fit the 6204 bearing kit."),
    ("GG-001", "Grease gun",
     "A lever grease gun that takes the 100 g tube."),
]

PAGES = {"returns": RETURNS, "refunds": REFUNDS, "shipping": SHIPPING,
         "damaged": DAMAGED, "warranty": WARRANTY, "orders": ORDERS,
         "payments": PAYMENTS, "safety": SAFETY, "bulk": BULK,
         "privacy": PRIVACY, "care": CARE, "stock": STOCK,
         "returns-2024": OLD_RETURNS}
for sku, name, blurb in PRODUCTS:
    PAGES[sku.lower()] = PRODUCT.format(sku=sku, name=name,
                                        blurb=blurb)

if __name__ == "__main__":
    texts = PAGES.values()
    chars = sum(len(t) for t in texts)
    words = sum(len(t.replace("#", " ").split()) for t in texts)
    tokens = round(chars / 4, -2)  # rough rule: 4 characters a token
    print(f"{len(PAGES)} pages, {words:,} words, {chars:,} characters,"
          f" about {tokens:,.0f} tokens")
