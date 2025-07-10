# Odoo API

# Base Products:

### - [GET] `/api/v1/base-product`:

Endpoint for listing a supplier’s own set of base products.

Query params:

```
"page": integer | optional
"per_page": integer | optional
"search_token": string | optional
"base_product_id": string | optional
"supplier_product_id": integer | optional
"internal_product_id": string | optional
```

**Response Example:**

```json
[
  {
    "suppler_prodcut_id": "110774",
    "internal_product_id": "123",
    "base_product_id": "650",
    "unit": "box",
    "unit_count": 144,
    "base_product_name": "ليبتون شاي اسود - 25 فتلة",
    "suppler_prodcut_name": "ليبتون شاي اسود - 25 فتلة (كرتونة) -- كرتونة",
    "image_thumbnail": "https://cdn.cartona.com/production/images/base_product/image/650/thumb_107.png",
    "median_price": 4035.0,
    "tax_percentage": 0.0,
    "selling_price": 3900.00,
    "available_stock_quantity": 1000,
    "remind_me_at_stock": 1,
    "max_order": 100,
    "min_order": 1,
    "in_stock": true,
    "is_bundle": false,
    "is_published": true,
    "sold_amount": 0,
    "front_margin": null,
    "back_margin": true,
    "notes": ""
  },
  ...
]
```

### - [POST] `/api/v1/base-product/bulk-update`:

Endpoint for updating a supplier’s own set of base products

Body params:

```json
[{
    "supplier_code": string | conditional,

    "supplier_product_id": string | conditional,
    "internal_product_id": string | conditional,
    "base_product_id": string | conditional,
    "unit": string | conditional,
    "unit_count": integer | conditional,
    
    "in_stock": boolean | optional,
    "available_stock_quantity": integer | optional,
    "min_order": integer | optional,
    "max_order": integer | optional,
    "is_published": boolean | optional,
    "selling_price": float | optional,
    "remind_me_at_stock": integer | optional,
    "notes": string | optional
}]
```

**Notes:**

- To identify the record being updated, either of the following should be provided:
    - `supplier_product_id`
    - `internal_product_id`
        - note: `supplier_product_id` takes precedence over `internal_product_id`
    - `base_product_id` in addition to `unit` and `unit_count`
- The `supplier_code` parameter can be used to target the product of a specific supplier
- values for parameter `unit` can be one of the following: **box, can, bottle, kg, piece, dozen, bag, packet, plate, glass, pallet, jar, shrink, ton, saddlebag, roll, tissue, cone, coil, bunch, strip, recharge_card, mat**

### - [POST] `/api/v1/base-product/bulk-update-stock`:

Endpoint for updating the stock for supplier’s own set of base products

Body params:

```json
[{
    "base_product_id": string | required
    "available_stock_quantity": integer | required
}]
```

**Notes:**

- Each product that falls under a `base_product_id` would have its stock updated according to each individual `unit_count` (available_stock_quantity/unit_count).

# Orders:

### - [GET] `/api/v1/orders/pull-orders`:

Endpoint for fetching newly created/updated orders

**Note:** we can control how orders are pulled depending on the syncing strategy

**Response Example:**

```json
[
  {
    "hashed_id": "pPX2wRNM",
    "supplier_code": "3",
    "edited_by_admin": true,
    "delivery_day": null,
    "status": "assigned_to_salesman",
    "delivered_by": "delivered_by_cartona",
    "pickup_date": "2023-04-27",
    "pickup_otp": "123456",
    "retailer_preferred_delivery_date": "2023-04-28",
    "estimated_delivery_day": "2023-04-28",
    "cancellation_reason": "",
    "return_reason": null,
    "total_price": 51,
    "applied_supplier_rebate": 250.0,
    "cartona_credit": 0,
    "installment_cost": 0,
    "wallet_top_up": 0,
    "distribution_route_code": "001#033",
    "retailer": {
      "retailer_name": "Test5555",
      "retailer_number": "+201003150160",
      "retailer_number2": "+201003150140",
      "retailer_address": "Test777777777, Test66666666, Test88888888",
      "address_notes": "Test88888888"
    },
    "order_details": [
      {
        "id": 14527894,
        "supplier_product_id": "110774",
        "internal_product_id": "479",
        "base_product_id": "650",
        "unit": "box",
        "unit_count": 144,
        "product_name": "جهينة حليب بخيره كامل الدسم - 1 لتر   -- كرتونة",
        "amount": 5,
        "selling_price": 1,
        "applied_supplier_discount": 0,
        "applied_cartona_discount": 0,
        "comment": null
      }, ...
    ]
  }
]
```

### - [POST] `/api/v1/orders/update-order-status` (bulk):

Endpoint for updating the status for a supplier’s orders

Body params:

```json
[{
    "hashed_id": string | required
    "status": string | required
    "retailer_otp": string | conditional
    "estimated_delivery_day": string | optional
    "cancellation_reason": string | optional
    "delivery_day": string | optional
}]
```

**Notes:**

- values for parameter `status` can be one of the following: **synced, pending, approved, assigned_to_salesman, delivered, cancelled_by_supplier**
    
    <aside>
    💡  **`synced`** is not an actual state for orders, it’s used to confirm the reception of the order’s data, so it doesn’t appear again in the `pull-orders` endpoint.  ****
    
    </aside>
    
- values for parameter `cancellation_reason` can be one of the following: **out_of_stock, cannot_deliver_the_order, supplier_asked_me_to_cancel, delayed_order, pending_order_without_action, removed_items, supplier_attitude, missing_items, expired_products, different_prices, different_products**

### - [POST] `/api/v1/orders/update-order-status/<hashed_id>` (single):

This endpoint is for updating a single order. But will respond with an error if the update fails (unlike the bulk endpoint).

 Body params:

```json
{
    "hashed_id": string | required
    "status": string | required
    "retailer_otp": string | conditional
    "estimated_delivery_day": string | optional
    "cancellation_reason": string | optional
    "delivery_day": string | optional
} 
// just like the bulk endpoint except you send an object
// instead on an array of objects
```

**Notes:**

- This is endpoint useful when sending OTP and want to block marking the order as delivered until you get confirmation that the otp is correct.

### - [POST] `/api/v1/orders/update-order-details` (bulk):

Endpoint for updating a supplier’s orders’ content 

Body params:

```json
[{
    "hashed_id": string | required
    "order_details": {
        "id": integer | required for non-new order,

        "supplier_product_id": string | required unless `internal_product_id` is provided,
        "internal_product_id": string | required unless `supplier_product_id` is provided,
        "base_product_id": string | conditional,
        "unit": string | conditional,
        "unit_count": integer | conditional,

        "amount": integer | optional,
        "price": number | optional,
        "cancelled": boolean | optional,
        "comment": string | optional
    }
}]
```

example: 

```json
[
    {
        "hashed_id": "L7b3xpOP",
        "order_details": [
            {//changing amount
                "internal_product_id": "68168538",
                "id": 11971867,
                "amount": 6.0
            },
            {//adding an order detail
                "supplier_product_id": "110774",
                "amount": 8.0,
                "price": 33
            },
            {//cancelling an order detail
                "id": 11971870,
                "cancelled": true
            }
        ]
    }
]
```

**Notes:**

- To identify the supplier product within an order detail, either of the following should be provided:
    - `supplier_product_id`
    - `internal_product_id`
        - note: `supplier_product_id` takes precedence over `internal_product_id`
    - `base_product_id` in addition to `unit` and `unit_count`

## Cartona Order Cycle Guide

Orders in Cartona can have one of the following statuses: 

- **pending:** when the order is first created by the retailer, in this state the order can be edited, or cancelled by the retailer
- **editing:** the retailer started editing the order, in this case, the `pull_orders` API will return that this order is *editing*, and the supplier should not be able to take action on it until it is back to pending.
- **approved:** the supplier approved the order, in this state, the retailer can only cancel the order
- **cancelled_by_retailer**: the retailer cancelled the order when it was in pending or approved state
- **assigned_to_salesman**: the supplier marks the order as shipped, from this state, the retailer cannot edit or cancel the order
- **delivered:** the supplier marked the order as delivered, no further edits are possible on the order from both supplier and retailer
- **cancelled_by_supplier:** the supplier can cancel the order if it was (pending, approved, assigned_to_salesman)
- **returned:** The supplier can mark the order as returned (retailer did not receive the order) if the order was in state *assigned_to_salesman*

The supplier can edit the order items in the following states: (pending, approved, assigned_to_salesman)

## Some extra features in Cartona orders:

- The retailer can use Cartona credits in an order, for example, if the order total price is 100, the retailer can use 10 from his credit. In this case, the supplier will take 90 from the retailer when delivering the order, and the remaining 10 will be collected from Cartona.
- The retailer can charge his wallet (wallet top up) in an order, so if the order total price is 100, the user can choose to put an extra 20 when making the order to charge his wallet, so the supplier will collect 120 from the retailer instead of 100, and Cartona will collect from the supplier later.
- The retailer can make installment orders, in this case, all of the order value will be collected from Cartona.
- If an order is installment or has wallet top-up, it will require an OTP to be marked as delivered, so it’s important to have the option to send OTP when updating order status to delivered.
- Cartona supports offers on products, for example, if a product’s price is 10, it can have an offer that makes the price 7.
    - Each product in an offer can have a max amount that retailers can’t exceed with the offer price, but retailers can add more with the normal price. For example, if the product in the offer has price 7 and max quantity 2, and the retailer wants to order 5 of that item. The order items will be as follows:
    
    ```json
    [
    	{
    	"internal_product_id": "52",
    	"price": 7,
      "applied_cartona_discount": 1,
      "applied_supplier_discount": 2,
    	"amount": 2
    	},
    	{
    	"internal_product_id": "52",
    	"price": 10,
      "applied_cartona_discount": 0,
      "applied_supplier_discount": 0,
    	"amount": 3
    	}
    ]
    ```
    
    - The offers in Cartona can be covered by the supplier or Cartona, for example, if the normal product’s price is 10, and in the offer is priced at 7, the 3EGP discount can be divided as follows:
        - 2EGP from the supplier
        - 1EGP from Cartona
        
        So in the case of Cartona covering some offers, the supplier will collect this difference from Cartona.
        
- Cartona system supports giving unique codes to both retailers and distribution routes, in case the supplier’s system supports this. In the case of retailers Cartona will assign a retailer a new code if it is his first order from the supplier, otherwise, it will be the same code.
- Cartona system supports handling multiple accounts from a single ERB, for example, if the supplier has a different price list for wholesale and wholesale to wholesale, in this case, all requests should send an extra `internal_supplier_code` to differentiate between them.  If not sent while having multiple accounts under the same token, it will update/fetch all products under the different accounts. When pulling the orders, the supplier_code will always be specified.
- For the order financials:
    - `total_price` = sum(order_detail.price * amount) (meaning the actual value of the total ordered products)
    - `cartona_credit` = the amount used from cartona credit
    - `installment_cost` = the amount that will be paid in installments with cartona (mostly it should equal the `total_price` - `cartona_credit`, if this is not the case, this means that the remaining from total_price will be paid in cash)
    - `wallet_topup` = the extra amount the retailer will pay to charge his cartona wallet (always in cash when the order is delivered)
- order details discount:
    - `selling_price` = final price per piece (after discounts)
    - `applied_supplier_discount` = supplier discount per piece
    - `applied_cartona_discount` = cartona discount per piece

**Order example:**

```json
{
    "hashed_id": "GMNvpbLM",
    "supplier_code": "1",
    "status": "pending",
    "delivery_day": null,
    "estimated_delivery_day": "2023-09-09",
    "cancellation_reason": "",
    "return_reason": null,
    "total_price": 3040,
    "cartona_credit": 50,
    "installment_cost": 2990,
    "wallet_top_up": 100,
    "distribution_route_code": "001#033",
    "retailer": {
      "retailer_name": "حياه ماركت",
      "retailer_code": "A00315",
      "retailer_number": "+201066313459",
      "retailer_number2": "+2000061774",
      "retailer_address": "عبدالسلام عارف، السرايا, سان ستيفانو, ",
      "address_notes": ""
    },
    "note_message": null,
    "order_details": [
      {
        "id": 11973734,
        "internal_product_id": "904#2",
        "product_name": "بيبسي ستار - 330 ملة",
        "amount": 10,
        "selling_price": 200,
        "applied_supplier_discount": 8,
        "applied_cartona_discount": 10,
        "comment": null
      },
      {
        "id": 11973735,
        "internal_product_id": "1679#2",
        "product_name": "الباشا سكر نقي صافي - 1 كجم",
        "amount": 4,
        "selling_price": 260,
        "applied_supplier_discount": 0,
        "applied_cartona_discount": 0,
        "comment": null
      }
    ]
  }
```

- To mark an order as synced after pulling it, simply send status `synced`
- Default supplier codes meaning (can be changed according to agreement):
    - 1: تجزئة
    - 2: جملة
    - 3: جملة الجملة
- There is an API to update a single order and get error if not updated. It will be the same  endpoint but called with a specific order hash ID: [api/v1/order/update-order-status/<order_hash>](https://supplier-integrations.cartona.space/api/v1/order/update-order-status/%3Corder_hash%3E). This is useful when sending OTP and want to block marking the order as delivered until you get confirmation that the otp is correct