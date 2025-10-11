import operator
from typing import TypedDict, Annotated, List, Dict
import json
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
import os 
from dotenv import load_dotenv

# --- Environment and API Key Setup ---
load_dotenv()
# Ensure your GOOGLE_API_KEY is in your .env file
os.environ["GOOGLE_API_KEY"] = "AIzaSyC4nAZzkyk76sNGN2Bmz6QE9tLoUQ2rZgQ"# <- This should be in your .env file

# --- 1. Pydantic Models for Structured LLM Outputs ---

class RequirementChecklist(BaseModel):
    """A model to structure the dynamically generated requirement checklist."""
    category: str = Field(description="The general category of the item. e.g., 'Car', 'Laptop'")
    essential_checklist: List[str] = Field(description="A list of ABSOLUTELY ESSENTIAL attributes. The agent CANNOT proceed without these. (e.g., for a car, 'car_type' and 'price_range'). Use snake_case.")
    optional_checklist: List[str] = Field(description="A list of OPTIONAL, nice-to-have attributes. (e.g., for a car, 'make', 'model', 'color'). Use snake_case.")

class AISuggestions(BaseModel):
    """A model to structure the AI-generated suggestions for an admin."""
    suggestions: List[str] = Field(description="A list of suggested items or services based on the user's initial request. e.g., ['Delivery & Setup', 'On-site Technician']")

class VendorScores(BaseModel):
    """A model to structure the AI-generated scores for a vendor's quote."""
    relevance_score: int = Field(description="Score (0-100) for how well the vendor's answers match the requirement.")
    profile_score: int = Field(description="Score (0-100) based on the vendor's profile and perceived reliability from their answers.")
    final_score: int = Field(description="A final weighted score (0-100) combining relevance, profile, and other factors.")

# --- 2. Agent State Definition ---

class AgentState(TypedDict):
    initial_query: str
    category: str
    essential_checklist: List[str]
    optional_checklist: List[str]
    extracted_requirements: Dict[str, str]
    messages: Annotated[list[AnyMessage], operator.add]
    next: str

# --- 3. The Main Agent Handler Class ---

class AgentHandler:
    def __init__(self):
        # Initialize LLMs
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", convert_system_message_to_human=True)
        self.checklist_generator_llm = self.llm.with_structured_output(RequirementChecklist)
        self.suggestion_generator_llm = self.llm.with_structured_output(AISuggestions)
        self.scoring_llm = self.llm.with_structured_output(VendorScores)
        
        # Build and compile the graph
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    # --- 4. Graph Node Definitions (with improved logic) ---
    
    def _conditional_start_node(self, state: AgentState) -> str:
        """Routes to the correct starting node."""
        if "essential_checklist" not in state or not state["essential_checklist"]:
            return "generate_checklist"
        return "update_and_parse"

    def _generate_checklist_node(self, state: AgentState) -> Dict:
        """Dynamically generates essential and optional checklists from the initial query."""
        print("---AGENT: GENERATING SMART CHECKLIST---")
        response = self.checklist_generator_llm.invoke(
            f"The user wants to buy an item. Here is their request: '{state['initial_query']}'. "
            "What is the category of this item? What is the checklist of absolutely essential requirements I must ask for? "
            "And what is a checklist of optional, nice-to-have requirements?"
        )
        return {
            "category": response.category,
            "essential_checklist": response.essential_checklist,
            "optional_checklist": response.optional_checklist,
            "messages": [SystemMessage(content=f"Generated checklist for {response.category}. Essentials: {response.essential_checklist}.")]
        }

    def _update_and_parse_node(self, state: AgentState) -> Dict:
        """Parses the latest user message to extract requirements using robust JSON cleaning."""
        print("---AGENT: PARSING USER RESPONSE---")
        latest_user_message = state['messages'][-1].content

        prompt = f"""You are a data extraction assistant. Your sole job is to extract information from the user's message and return it as a JSON object.
        The user wants to buy a: {state['category']}.
        The fields you must look for are: {', '.join(state['essential_checklist'] + state['optional_checklist'])}.
        --- EXAMPLES ---
        User Message: "I need a family-friendly SUV, maybe for around 30 lakhs"
        Your JSON Output: {{"car_type": "SUV", "price_range": "around 30 lakhs"}}
        User Message: "I want a gaming laptop under $1500. Not sure about the brand, any is fine."
        Your JSON Output: {{"primary_use": "gaming", "budget": "under $1500", "brand": "Any"}}
        --- END OF EXAMPLES ---
        Now, perform the same task. The user's latest message is: "{latest_user_message}"
        Return ONLY the JSON object. Do not wrap it in markdown.
        """
        response = self.llm.invoke(prompt)
        updated_reqs = state.get('extracted_requirements', {}).copy()
        
        try:
            raw_content = response.content
            start_index = raw_content.find('{')
            end_index = raw_content.rfind('}')
            if start_index != -1 and end_index != -1:
                clean_json_str = raw_content[start_index : end_index + 1]
                updated_reqs.update(json.loads(clean_json_str))
        except (json.JSONDecodeError, TypeError) as e:
            print(f"DEBUG: Failed to parse JSON. Error: {e}. Raw: {response.content}")

        return {"extracted_requirements": updated_reqs}

    def _ask_question_node(self, state: AgentState) -> Dict:
        """Formulates the next question to ask the user based on missing information."""
        print("---AGENT: FORMULATING QUESTION---")
        extracted_keys = state.get('extracted_requirements', {}).keys()
        missing_reqs = [req for req in (state['essential_checklist'] + state['optional_checklist']) if req not in extracted_keys]

        prompt = f"""Based on the conversation history and the user's goal to buy a {state['category']}, formulate the next question to ask.
        The user has already provided this information: {state['extracted_requirements']}.
        You still need to find out about the following: {missing_reqs}.
        Focus on the most important missing items first. Ask for one or two pieces of information at a time. Make your question friendly and conversational."""
        
        response = self.llm.invoke(prompt)
        # NOTE: We return the agent's message and a 'next' state to pause for the API.
        return {"messages": [SystemMessage(content=response.content)], "next": "wait_for_user_input"}

    def _router_node(self, state: AgentState) -> str:
        """Routes the conversation based on whether essential requirements have been met."""
        print("---AGENT: ROUTING---")
        extracted_keys = state.get('extracted_requirements', {}).keys()
        missing_essential_reqs = [req for req in state['essential_checklist'] if req not in extracted_keys]
        
        if not missing_essential_reqs:
            print("-> All ESSENTIAL requirements met. Proceeding to summary.")
            return "final_summary"
        else:
            print(f"-> Missing essential requirements: {missing_essential_reqs}. Asking user.")
            return "ask_question"

    def _final_summary_node(self, state: AgentState) -> Dict:
        """Creates and returns the final summary message."""
        print("---AGENT: FINAL SUMMARY---")
        final_reqs = state.get('extracted_requirements', {})
        summary_message = f"Great! Your requirement for a '{state['category']}' is ready to be sent for processing. Here is the summary:\n"
        for key in state['essential_checklist'] + state['optional_checklist']:
            if key in final_reqs:
                summary_message += f"- {key.replace('_', ' ').title()}: {final_reqs.get(key, 'N/A')}\n"
        return {"messages": [SystemMessage(content=summary_message)], "next": "end_conversation"}

    # --- 5. Graph Definition (preserved from our fixes) ---

# --- 5. Graph Definition (Corrected) ---

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add all the nodes to the graph
        workflow.add_node("generate_checklist", self._generate_checklist_node)
        workflow.add_node("update_and_parse", self._update_and_parse_node)
        workflow.add_node("ask_question", self._ask_question_node)
        workflow.add_node("final_summary", self._final_summary_node)
        
        # --- START OF FIX ---
        
        # Set a CONDITIONAL entry point. The graph will now start by calling
        # our routing function to decide where to go first.
        workflow.set_conditional_entry_point(
            self._conditional_start_node,
            {
                # If the function returns "generate_checklist", go to that node.
                "generate_checklist": "generate_checklist",
                # If it returns "update_and_parse", go to that node instead.
                "update_and_parse": "update_and_parse"
            }
        )
        
        # --- END OF FIX ---
        
        workflow.add_edge("generate_checklist", "update_and_parse")
        
        workflow.add_conditional_edges(
            "update_and_parse",
            self._router_node,
            {"ask_question": "ask_question", "final_summary": "final_summary"}
        )
        
        workflow.add_edge("ask_question", END)
        workflow.add_edge("final_summary", END)
        return workflow
    # --- 6. Public Methods for FastAPI (preserved from our fixes) ---
    
    async def run_first_turn(self, initial_query: str) -> Dict:
        initial_state = {"initial_query": initial_query, "messages": [HumanMessage(content=initial_query)]}
        final_state = initial_state.copy()
        async for event in self.app.astream(initial_state, {"recursion_limit": 100}):
            for node_name, node_output in event.items():
                final_state.update(node_output)
            if "ask_question" in event or "final_summary" in event:
                break
        return final_state

    async def run_next_turn(self, current_state: Dict, user_input: str) -> Dict:
        current_state["messages"].append(HumanMessage(content=user_input))
        final_state = current_state.copy()
        async for event in self.app.astream(current_state, {"recursion_limit": 100}):
            for node_name, node_output in event.items():
                final_state.update(node_output)
            if "ask_question" in event or "final_summary" in event:
                break
        return final_state
    
    # --- Other Public Methods (unchanged) ---

    async def generate_suggestions(self, initial_query: str) -> List[str]:
        print("---AGENT: GENERATING ADMIN SUGGESTIONS---")
        prompt = f"Based on '{initial_query}', suggest specific line items for a procurement request."
        response = self.suggestion_generator_llm.invoke(prompt)
        return response.suggestions

    async def score_vendor_quote(self, requirement: Dict, quote: Dict) -> Dict:
        print(f"---AGENT: SCORING VENDOR QUOTE FOR {quote.get('vendor_name')}---")
        # (This logic remains the same as before)
        context = f"""
        Original User Requirement: {requirement.get('initial_query')}
        Finalized Items: {', '.join(requirement.get('finalized_items', []))}
        Vendor's Quote Amount: ${quote.get('amount')}
        Items Covered by Vendor: {quote.get('items_covered')}
        Vendor's Answers to Questionnaire: {json.dumps(quote.get('answers'), indent=2)}
        Task: Provide a score for this vendor based on Relevance (0-100), Profile (0-100), and a Final Score (0-100).
        """
        response = self.scoring_llm.invoke(context)
        return response.dict()

    def get_agent_response(self, state: Dict) -> str:
        return state["messages"][-1].content

    def is_conversation_complete(self, state: Dict) -> bool:
        return state.get("next") == "end_conversation"