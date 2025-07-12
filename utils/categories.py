# utils/categories.py
from enum import Enum
from typing import List

class ExpenseCategory(Enum):
    """Expense categories for classification"""
    FOOD = "Food & Dining"
    TRANSPORT = "Transportation"
    SHOPPING = "Shopping"
    ENTERTAINMENT = "Entertainment"
    UTILITIES = "Utilities"
    HEALTHCARE = "Healthcare"
    TRAVEL = "Travel"
    EDUCATION = "Education"
    OTHER = "Other"

# Category keywords for intelligent classification
CATEGORY_KEYWORDS = {
    ExpenseCategory.FOOD: [
        'restaurant', 'coffee', 'lunch', 'dinner', 'breakfast', 'food', 'cafe',
        'starbucks', 'mcdonalds', 'pizza', 'burger', 'sandwich', 'meal',
        'grocery', 'supermarket', 'eating', 'dining', 'kitchen', 'snack',
        'takeout', 'delivery', 'restaurant', 'bistro', 'diner', 'buffet'
    ],
    
    ExpenseCategory.TRANSPORT: [
        'uber', 'taxi', 'gas', 'fuel', 'parking', 'bus', 'train', 'metro',
        'subway', 'flight', 'car', 'vehicle', 'transport', 'ride', 'lyft',
        'airline', 'airport', 'toll', 'maintenance', 'repair', 'insurance'
    ],
    
    ExpenseCategory.SHOPPING: [
        'amazon', 'store', 'shop', 'buy', 'purchase', 'clothes', 'clothing',
        'electronics', 'gadget', 'book', 'item', 'product', 'order',
        'mall', 'retail', 'boutique', 'department', 'online', 'shopping'
    ],
    
    ExpenseCategory.ENTERTAINMENT: [
        'movie', 'cinema', 'game', 'concert', 'show', 'entertainment',
        'netflix', 'spotify', 'subscription', 'streaming', 'music',
        'theater', 'club', 'bar', 'party', 'event', 'ticket'
    ],
    
    ExpenseCategory.UTILITIES: [
        'electric', 'electricity', 'water', 'internet', 'phone', 'utility',
        'bill', 'rent', 'mortgage', 'insurance', 'cable', 'wifi',
        'heating', 'cooling', 'service', 'maintenance'
    ],
    
    ExpenseCategory.HEALTHCARE: [
        'doctor', 'hospital', 'pharmacy', 'medicine', 'health', 'medical',
        'dentist', 'clinic', 'prescription', 'treatment', 'therapy',
        'checkup', 'appointment', 'specialist', 'emergency'
    ],
    
    ExpenseCategory.TRAVEL: [
        'hotel', 'airbnb', 'flight', 'vacation', 'trip', 'travel', 'booking',
        'accommodation', 'tourist', 'resort', 'cruise', 'luggage',
        'passport', 'visa', 'excursion', 'tour'
    ],
    
    ExpenseCategory.EDUCATION: [
        'school', 'university', 'college', 'course', 'class', 'tuition',
        'book', 'education', 'learning', 'training', 'workshop',
        'certification', 'degree', 'academic', 'student'
    ]
}

def categorize_expense(description: str) -> str:
    """
    Categorize expense based on description keywords
    
    Args:
        description: Expense description text
        
    Returns:
        Category name as string
    """
    if not description:
        return ExpenseCategory.OTHER.value
    
    description_lower = description.lower()
    
    # Score each category based on keyword matches
    category_scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in description_lower)
        if score > 0:
            category_scores[category] = score
    
    # Return category with highest score
    if category_scores:
        best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
        return best_category.value
    
    return ExpenseCategory.OTHER.value

def get_all_categories() -> List[str]:
    """Get list of all available categories"""
    return [category.value for category in ExpenseCategory]

def get_category_keywords(category_name: str) -> List[str]:
    """Get keywords for a specific category"""
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category.value == category_name:
            return keywords
    return []