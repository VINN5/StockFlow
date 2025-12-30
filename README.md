# StockFlow - Inventory & POS System 🇰🇪

A modern, web-based inventory management and point-of-sale (POS) system built for small to medium supermarkets and shops in Kenya.

Live Demo: Coming soon! (Deployment in progress)

## Features

- **Product Management**  
  Add, edit, delete, and search products with name, description, unit, purchase price, selling price, min/max stock, and current quantity.

- **Suppliers Management**  
  Manage suppliers with contact details. Add new suppliers on the fly during purchases.

- **Purchases**  
  Record stock intake from suppliers, automatically increase product quantity, and generate printable purchase receipts.

- **POS Sales**  
  Fast point-of-sale interface: search products, add to cart, calculate total in KSh, checkout, decrease stock, and print sales receipt.

- **Dashboard**  
  Real-time overview:
  - Total products
  - Stock value (cost)
  - Potential sales value (selling price)
  - Low stock alerts
  - Total sales

- **User Roles & Security**  
  - Admin: full access (sees costs, manages users)
  - Cashier: limited access (no cost info, no user management)

- **Responsive Design**  
  Works perfectly on desktop, tablet, and phone (Progressive Web App ready)

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: MongoDB (Atlas cloud)
- **Frontend**: Bootstrap 5, Font Awesome, vanilla JavaScript
- **Authentication**: Flask-Bcrypt
- **Deployment**: Render (free tier)

## Local Setup

1. Clone the repo
   ```bash
   git clone https://github.com/VINN5/stockflow.git
   cd stockflow
