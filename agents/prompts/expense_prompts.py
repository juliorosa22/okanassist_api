# agents/prompts/expense_prompts.py
"""
Concise system prompts for the ExpenseAgent
Optimized for minimal token usage while maintaining parsing accuracy
"""

from typing import Dict, Any

class ExpensePrompts:
    """Token-optimized prompts for expense agent"""
    
    @staticmethod
    def expense_parsing(user_context: Dict[str, Any]) -> str:
        """Compact expense parsing prompt"""
        
        return f"""Parse expense from natural language. User: {user_context["language"]}, {user_context["currency"]}, {user_context["country"]}

Extract: amount, currency, description, category, language

Categories: Food & Dining, Transportation, Shopping, Entertainment, Utilities, Healthcare, Travel, Education, Other

JSON response:
{{"success": true, "amount": 4.50, "currency": "USD", "description": "Coffee", "category": "Food & Dining", "detected_language": "en", "confidence": 0.9}}

Examples:
- "Coffee $4.50" → USD, Food & Dining, en
- "Café €5.00" → EUR, Food & Dining, es  
- "Gasolina R$ 50" → BRL, Transportation, pt
- "Uber 12 euros" → EUR, Transportation, en

Currency detection: $→USD, €→EUR, R$→BRL
Language: café/compré→es, café/comprei→pt, default→en
Categories: coffee/lunch→Food, uber/gas→Transportation, amazon/store→Shopping

If missing amount or description, set success=false."""

    @staticmethod
    def success_confirmation(language: str, amount: float, currency: str, description: str, category: str) -> str:
        """Compact success confirmation prompt"""
        
        return f"""Generate expense confirmation in {language}.

Expense: {amount} {currency} for {description} ({category})

Format: "✅ [Expense saved/Gasto guardado/Despesa salva]: [symbol]{amount} for/para {description} ({category})"

Currency symbols: USD→$, EUR→€, BRL→R$
Languages: en→"Expense saved", es→"Gasto guardado", pt→"Despesa salva"

Be concise, friendly, use correct currency symbol."""

    @staticmethod
    def error_response(language: str, error_message: str) -> str:
        """Compact error response prompt"""
        
        return f"""Generate helpful expense error in {language}. Error: {error_message}

Format: "❌ [brief apology] [suggest format with currency example]"

Examples by language:
- en: "❌ I couldn't find the amount. Try: 'Coffee $4.50'"
- es: "❌ No encontré el monto. Prueba: 'Café €4.50'" 
- pt: "❌ Não encontrei o valor. Tente: 'Café R$ 4.50'"

Use appropriate currency for region."""

    @staticmethod
    def welcome_message(language: str, currency: str) -> str:
        """Compact welcome message prompt"""
        
        return f"""Generate expense welcome in {language} for new user.

Default currency: {currency}
Format: "👋 Welcome! No expenses yet. Try: 'Coffee [symbol]4.50'"

Currency symbols: USD→$, EUR→€, BRL→R$
Be encouraging, show example with correct symbol."""

    @staticmethod
    def summary_response(language: str, currency: str, total_amount: float, total_count: int, average_amount: float, days: int) -> str:
        """Compact summary response prompt"""
        
        return f"""Generate expense summary in {language}.

Data: {total_amount} {currency} total, {total_count} expenses, {average_amount} {currency} average, {days} days

Format: "📊 Last {days} days: [symbol]{total_amount} total, {total_count} expenses, avg [symbol]{average_amount}"

Currency symbols: USD→$, EUR→€, BRL→R$
Languages: en→"Last", es→"Últimos", pt→"Últimos"

Be concise, use correct symbols."""

class ExpenseFallbacks:
    """Ultra-compact fallback responses"""
    
    SUCCESS = {
        "en": "✅ Expense saved: ${amount} for {description} ({category})",
        "es": "✅ Gasto guardado: €{amount} para {description} ({category})", 
        "pt": "✅ Despesa salva: R$ {amount} para {description} ({category})"
    }
    
    ERROR = {
        "en": "❌ Error processing expense. Try: 'Coffee $4.50'",
        "es": "❌ Error procesando gasto. Prueba: 'Café €4.50'",
        "pt": "❌ Erro processando despesa. Tente: 'Café R$ 4.50'"
    }
    
    WELCOME = {
        "en": "👋 Welcome! No expenses yet. Try: 'Coffee $4.50'",
        "es": "👋 ¡Bienvenido! Sin gastos aún. Prueba: 'Café €4.50'",
        "pt": "👋 Bem-vindo! Sem despesas ainda. Tente: 'Café R$ 4.50'"
    }
    
    SUMMARY = {
        "en": "📊 Last {days} days: ${total} total, {count} expenses",
        "es": "📊 Últimos {days} días: €{total} total, {count} gastos",
        "pt": "📊 Últimos {days} dias: R$ {total} total, {count} despesas"
    }
    
    @staticmethod
    def get_currency_symbol(currency: str) -> str:
        """Get currency symbol"""
        symbols = {"USD": "$", "EUR": "€", "BRL": "R$"}
        return symbols.get(currency, "$")
    
    @staticmethod
    def format_success(language: str, amount: float, currency: str, description: str, category: str) -> str:
        """Format success message with correct currency symbol"""
        symbol = ExpenseFallbacks.get_currency_symbol(currency)
        template = ExpenseFallbacks.SUCCESS.get(language, ExpenseFallbacks.SUCCESS["en"])
        
        # Replace currency symbol in template
        if language == "es":
            template = template.replace("€", symbol)
        elif language == "pt":
            template = template.replace("R$ ", symbol)
        else:
            template = template.replace("$", symbol)
            
        return template.format(amount=amount, description=description, category=category)
    
    @staticmethod
    def format_summary(language: str, currency: str, total_amount: float, total_count: int, days: int) -> str:
        """Format summary with correct currency symbol"""
        symbol = ExpenseFallbacks.get_currency_symbol(currency)
        template = ExpenseFallbacks.SUMMARY.get(language, ExpenseFallbacks.SUMMARY["en"])
        
        # Replace currency symbol
        if language == "es":
            template = template.replace("€", symbol)
        elif language == "pt":
            template = template.replace("R$ ", symbol)
        else:
            template = template.replace("$", symbol)
            
        return template.format(days=days, total=total_amount, count=total_count)
    
    @staticmethod
    def format_welcome(language: str, currency: str) -> str:
        """Format welcome with correct currency symbol"""
        symbol = ExpenseFallbacks.get_currency_symbol(currency)
        template = ExpenseFallbacks.WELCOME.get(language, ExpenseFallbacks.WELCOME["en"])
        
        # Replace currency symbol
        if language == "es":
            template = template.replace("€", symbol)
        elif language == "pt":
            template = template.replace("R$ ", symbol)
        else:
            template = template.replace("$", symbol)
            
        return template

# Token usage optimization:
# - Reduced from ~800 tokens to ~200 tokens per prompt (~75% reduction)
# - Removed verbose examples and explanations
# - Used compact JSON format
# - Consolidated currency/language rules
# - Smart fallbacks with dynamic currency symbols