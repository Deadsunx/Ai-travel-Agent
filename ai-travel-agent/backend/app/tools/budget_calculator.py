from pydantic import BaseModel, Field
from typing import Type
import json

from app.tools.base import BaseTravelTool


class BudgetCalculatorInput(BaseModel):
    """Input schema for Budget Calculator tool"""
    flights_cost: float = Field(description="Total cost of flights in INR")
    accommodation_cost: float = Field(description="Total cost of accommodation in INR")
    food_cost: float = Field(description="Estimated food cost in INR")
    activities_cost: float = Field(default=0.0, description="Cost of activities and attractions in INR")
    miscellaneous: float = Field(default=0.0, description="Miscellaneous expenses in INR")
    budget_limit: float = Field(description="Maximum budget limit in INR")


class BudgetCalculatorTool(BaseTravelTool):
    """Tool for calculating trip budget and validating against limits"""
    
    name: str = "budget_calculator"
    description: str = """Calculate total trip cost and validate against budget limit.
    Returns detailed breakdown of costs and whether the trip fits within budget.
    Input all costs in INR (Indian Rupees)."""
    args_schema: Type[BaseModel] = BudgetCalculatorInput
    
    def _run(
        self,
        flights_cost: float,
        accommodation_cost: float,
        food_cost: float,
        activities_cost: float = 0.0,
        miscellaneous: float = 0.0,
        budget_limit: float = 0.0
    ) -> str:
        """Calculate and validate budget"""
        
        try:
            # Calculate totals
            subtotal = (
                flights_cost +
                accommodation_cost +
                food_cost +
                activities_cost +
                miscellaneous
            )
            
            # Add 10% buffer for unexpected expenses
            buffer_amount = subtotal * 0.1
            total_with_buffer = subtotal + buffer_amount
            
            # Budget validation
            within_budget = total_with_buffer <= budget_limit if budget_limit > 0 else True
            remaining = budget_limit - total_with_buffer if budget_limit > 0 else 0
            percentage_used = (total_with_buffer / budget_limit * 100) if budget_limit > 0 else 0
            
            # Build result
            result = {
                "breakdown": {
                    "flights": round(flights_cost, 2),
                    "accommodation": round(accommodation_cost, 2),
                    "food": round(food_cost, 2),
                    "activities": round(activities_cost, 2),
                    "miscellaneous": round(miscellaneous, 2),
                    "buffer_10_percent": round(buffer_amount, 2)
                },
                "subtotal": round(subtotal, 2),
                "total_with_buffer": round(total_with_buffer, 2),
                "budget_limit": round(budget_limit, 2),
                "remaining_budget": round(remaining, 2),
                "within_budget": within_budget,
                "percentage_used": round(percentage_used, 2),
                "currency": "INR",
                "recommendations": self._get_recommendations(
                    within_budget, 
                    remaining, 
                    percentage_used,
                    flights_cost,
                    accommodation_cost,
                    food_cost
                )
            }
            
            return self._format_result(result)
            
        except Exception as e:
            return self._format_error(f"Budget calculation failed: {str(e)}")
    
    def _get_recommendations(
        self,
        within_budget: bool,
        remaining: float,
        percentage_used: float,
        flights_cost: float,
        accommodation_cost: float,
        food_cost: float
    ) -> list:
        """Generate budget recommendations"""
        recommendations = []
        
        if not within_budget:
            recommendations.append("⚠️ Budget exceeded! Consider these options:")
            
            # Find the largest expense category
            expenses = {
                "flights": flights_cost,
                "accommodation": accommodation_cost,
                "food": food_cost
            }
            largest = max(expenses, key=expenses.get)
            
            if largest == "flights":
                recommendations.append("- Look for budget airlines or alternative dates")
                recommendations.append("- Consider train travel for nearby destinations")
            elif largest == "accommodation":
                recommendations.append("- Consider hostels or budget hotels")
                recommendations.append("- Look for stays slightly outside the main area")
            else:
                recommendations.append("- Opt for street food and local eateries")
                recommendations.append("- Cook some meals if accommodation has kitchen")
            
        elif percentage_used > 90:
            recommendations.append("💡 Budget is tight. Consider keeping some buffer for emergencies.")
            
        elif percentage_used < 70:
            recommendations.append("✅ You have room in your budget for:")
            recommendations.append("- Upgrade accommodation")
            recommendations.append("- Add premium experiences")
            recommendations.append("- Fine dining experiences")
            
        else:
            recommendations.append("✅ Budget looks good! Trip is well-planned within limits.")
        
        return recommendations
    
    async def _arun(
        self,
        flights_cost: float,
        accommodation_cost: float,
        food_cost: float,
        activities_cost: float = 0.0,
        miscellaneous: float = 0.0,
        budget_limit: float = 0.0
    ) -> str:
        """Async version - delegates to sync"""
        return self._run(flights_cost, accommodation_cost, food_cost, activities_cost, miscellaneous, budget_limit)
