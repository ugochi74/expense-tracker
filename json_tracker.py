import json

def add_expenses(expenses, item, amount, category, next_id):
    new_expense = {
        #"id": len(expenses) + 1,   # simple id based on current list length
        "id": next_id, 
        "item": item,
        "amount": amount,
        "category": category
    }
    expenses.append(new_expense)
    return next_id + 1


def save_expenses(expenses, filename="expenses.json"):
    with open(filename, "w") as file:
        json.dump(expenses, file)

def load_expenses(filename="expenses.json"):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def show_expenses(expenses):
    for expense in expenses:
        print(f"ID: {expense['id']} | {expense['item']} - {expense['amount']} ({expense['category']})")
def delete_expense(expenses, expense_id):
    # 1. Create a new list outside the loop to hold what we want to keep
    updated_expenses = []
    
    # 2. Go through each expense
    for expense in expenses:
        # 3. If its ID doesn't match the one being deleted, keep it
        if expense["id"] != expense_id:
            updated_expenses.append(expense)
            
    # 4. Return the new list without the deleted item
    return updated_expenses

def total_expenses(expenses):
    total = 0
    for expense in expenses:
        total += expense["amount"]
    return total
def filter_by_category(expenses, category):
    filtered_list = []
    for expense in expenses:
        if expense["category"] == category:
            filtered_list.append(expense)
    return filtered_list
def edit_expense(expenses, expense_id, new_item, new_amount, new_category):
    for expense in expenses:
        if expense["id"] == expense_id:
            # 1. Update this expense's item, amount, and category fields
            expense["item"] = new_item
            expense["amount"] = new_amount
            expense["category"] = new_category
            
            # 2. Stop looping early — no need to check the rest
            break
            
    return expenses


#expenses = []

#next_id = 1
def get_next_id(expenses):
    if not expenses:
        return 1
    return max(expense["id"] for expense in expenses) + 1
    
expenses = load_expenses()
next_id = get_next_id(expenses)


while True:
    # 1. Show the menu and get the user's choice
    print("\n--- Expense Tracker Menu ---")
    choice = input("1. Add Expense\n2. Show Expenses\n3. Total Expenses\n4. Filter by Category\n5.  Delete Expenses\n6. Edit Expenses\n7. Quit\nChoose an option (1-7): ")
    print()  # Adds a blank line for cleaner formatting
    
    # 2. Decide what to do based on the choice
    if choice == "1":
        item = input("Enter the item name: ")
        
        # --- Start of validated amount block ---
        while True:
            try:
                amount = float(input("Enter the amount: "))
                break  # Leaves the validation loop if it is a number
            except ValueError:
                print("Invalid input. Please enter a number (e.g., 1500 or 12.50).")
        # --- End of validated amount block ---
        
        category = input("Enter the category: ")
        
        next_id = add_expenses(expenses, item, amount, category, next_id)
        print(f"'{item}' successfully added!")
        save_expenses(expenses)

        
    elif choice == "2":
        print("--- All Expenses ---")
        # Call our show function to print everything line-by-line
        show_expenses(expenses)
        
    elif choice == "3":
        # Call the total function and print its returned value
        total = total_expenses(expenses)
        print(f"Total Expenses: {total}")
        
    elif choice == "4":
        target_category = input("Enter the category to filter by: ")
        # Call filter function to get a brand new list of matches
        matches = filter_by_category(expenses, target_category)
        
        print(f"\n--- Expenses in '{target_category}' ---")
        # Reuse our show function to print just the filtered list
        show_expenses(matches)
    
    elif choice == "5":
        print("--- Delete an Expense ---")
        # Show current expenses first so the user can see the IDs
        show_expenses(expenses)
        print()
        
        while True:
            try:
                # Capture user input and instantly convert it to an integer
                id_to_delete = int(input("Enter the ID of the expense to delete: "))
                break
            except ValueError:
                print("Invalid ID! Please enter a valid ID number.")
        
        # Reassign expenses to the newly filtered list returned by the function
        expenses = delete_expense(expenses, id_to_delete)
        
        # Save to file right after the deletion sticks
        save_expenses(expenses)  # Assuming your save function is named save_expenses
        print(f"Expense ID {id_to_delete} has been removed and database updated!")
    



    elif choice == "6":
        print("--- Edit an Expense ---")
        # Show current expenses first so the user can look up the ID
        show_expenses(expenses)
        print()
        
        # Validate the ID selection input
        while True:
            try:
                expense_id = int(input("Enter the ID of the expense you want to edit: "))
                break
            except ValueError:
                print("Invalid ID! Please enter a valid ID number.")
                
        # Get the new details from the user
        new_item = input("Enter the new item name: ")
        
        # Validate the new amount input
        while True:
            try:
                new_amount = float(input("Enter the new amount: "))
                break
            except ValueError:
                print("Invalid input. Please enter a valid number for the amount.")
                
        new_category = input("Enter the new category: ")
        
        # Call edit function and update the local expenses variable
        expenses = edit_expense(expenses, expense_id, new_item, new_amount, new_category)
        
        # Save changes to disk immediately
        save_expenses(expenses)
        print(f"Expense ID {expense_id} has been successfully updated and saved!")



        
    elif choice == "7":
        # Break out of the infinite loop
        print("Thank you for using Expense Tracker. Goodbye!")
        break
        
    else:
        # Handle cases where the user types something invalid like "6" or "hello"
        print("Invalid choice! Please select a number between 1 and 7.")




#expenses = []
#add_expenses(expenses, "Lunch", 1500, "Food")
#add_expenses(expenses, "Bus", 300, "Transport")
#ssshow_expenses(expenses)