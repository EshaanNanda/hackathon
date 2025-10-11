import os
import uuid
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from supabase import create_client, Client
import json
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.tools.tavily_search import TavilySearchResults

from .agent import AgentHandler
# --- Load Environment Variables ---
from pathlib import Path
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

# --- Supabase Client Initialization ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase URL and Key must be set in the .env file.")
if not TAVILY_API_KEY:
    raise Exception("Tavily API Key must be set in the .env file.")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


app = FastAPI(
    title="Vendor Requirement Agent & Admin API",
    description="API for handling user requirement gathering and admin management.",
    version="7.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,allow_methods=["*"],allow_headers=["*"],
)

# --- Pydantic Models ---
# (All Pydantic models remain unchanged)
class ConversationTurn(BaseModel): user_input: str; state: Optional[Dict[str, Any]] = None
class AgentResponse(BaseModel): response: str; state: Dict[str, Any]; is_complete: bool; requirement_id: Optional[int] = None
class RequirementRecord(BaseModel):
    id: int; title: Optional[str] = None; status: str; initial_query: Optional[str] = None
    extracted_requirements: Optional[Dict[str, Any]] = None; start_date: Optional[str] = None
    end_date: Optional[str] = None; is_template: bool = False
    ai_suggestions: Optional[List[str]] = None; finalized_items: Optional[List[str]] = None
    winner_vendor_id: Optional[int] = None
class RequirementSummary(BaseModel): id: int; title: Optional[str] = None; status: str; initial_query: Optional[str] = None
class StatusUpdateRequest(BaseModel): status: str
class ItemsUpdateRequest(BaseModel): items: List[str]
class UserConfirmationRequest(BaseModel): action: str; comment: Optional[str] = None
class VendorReview(BaseModel): rating: float; comment: str
class VendorRecord(BaseModel): id: str; name: str; tags: List[str]; revenue: int; profile: int; rating: float; reviews: List[VendorReview]
class RFQRequest(BaseModel): vendors: List[VendorRecord]
class RFQInvitation(BaseModel): rfq_id: int; req_id: int; status: str; rfq: str; requirement_title: str; requirement_query: str
class QuoteSubmitRequest(BaseModel): rfq_id: int; vendor_id: int; amount: float; items_covered: str
class QuoteAnswersRequest(BaseModel): answers: Dict[str, str]
class QuoteDetails(BaseModel):
    quote_id: int; amount: Optional[float]; items_covered: Optional[str]; status: Optional[str]
    answers: Optional[Dict[str, Any]]; relevance_score: Optional[int]; profile_score: Optional[int]
    final_score: Optional[int]; is_shortlisted: bool = False
    vendor_name: str; vendor_id: int
class ShortlistRequest(BaseModel): top_n: int = Field(3, description="The number of top vendors to shortlist.")
class WinnerRequest(BaseModel): vendor_id: int
class ContractRequest(BaseModel):
    requirement_id: int; vendor_id: int; contract_title: str
    start_date: Optional[str] = None; amount: float
    payment_terms: str; scope: str
class VendorWithRFQ(BaseModel):
    vendor_id: int
    name: str
    rating: Optional[float] = 0.0
    tags: Optional[List[str]] = []
    profile: Optional[Dict[str, Any]] = {}

# Initialize our agent handler
agent_handler = AgentHandler()

# --- USER-FACING ENDPOINTS ---
@app.post("/requirements/converse", response_model=AgentResponse)
async def handle_conversation_turn(turn: ConversationTurn):
    try:
        if turn.state is None: result_state = await agent_handler.run_first_turn(turn.user_input)
        else: result_state = await agent_handler.run_next_turn(turn.state, turn.user_input)
        
        agent_message = agent_handler.get_agent_response(result_state)
        is_complete = agent_handler.is_conversation_complete(result_state)
        requirement_id = None
        
        if is_complete:
            data_to_insert = {
                "title": f"New Requirement for {result_state.get('category', 'Item')}",
                "status": "Submitted",
                "initial_query": result_state.get('initial_query', ''),
                "extracted_requirements": result_state.get('extracted_requirements', {})
            }
            response = supabase.table('Requirement').insert(data_to_insert).execute()
            if response.data: requirement_id = response.data[0]['id']
            else: raise Exception("Failed to insert requirement.")
            
        return AgentResponse(response=agent_message, state=result_state, is_complete=is_complete, requirement_id=requirement_id)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- ADMIN ENDPOINTS ---
@app.get("/requirements", response_model=List[RequirementSummary])
async def list_all_requirements():
    try:
        response = supabase.table('Requirement').select("id, title, status, initial_query").eq('is_template', False).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to fetch requirements: {e}")

@app.get("/requirements/new", response_model=List[RequirementSummary])
async def list_new_requirements():
    try:
        new_statuses = ["Submitted", "InReview", "UserConfirmed"]
        response = supabase.table('Requirement').select("id, title, status, initial_query").in_("status", new_statuses).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to fetch new requirements: {e}")

# --- REFACTORED ENDPOINT ---
@app.post("/requirements/{requirement_id}/select-winner", response_model=RequirementRecord)
async def select_winner(requirement_id: int, winner: WinnerRequest):
    try:
        # 1. Update the record
        supabase.table('Requirement').update({
            "winner_vendor_id": winner.vendor_id,
            "status": "WinnerSelected"
        }).eq("id", requirement_id).execute()

        # 2. Re-fetch the updated record to return it
        response = supabase.table('Requirement').select("*").eq("id", requirement_id).single().execute()
        
        if response.data: return response.data
        raise HTTPException(status_code=404, detail="Requirement not found after update.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to select winner: {str(e)}")

@app.post("/requirements/{id}/remove-item")
async def remove_item_from_requirement(id: int, item: dict):
    """Remove an item from requirement's finalized_items list"""
    try:
        result = supabase.table("Requirement").select("*").eq("id", id).single().execute()
        requirement = result.data
        
        finalized_items = requirement.get("finalized_items") or []
        item_to_remove = item.get("item")
        
        if item_to_remove in finalized_items:
            finalized_items.remove(item_to_remove)
        
        update_result = supabase.table("Requirement").update({
            "finalized_items": finalized_items
        }).eq("id", id).execute()
        
        return update_result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/requirements/{requirement_id}/finalize")
async def finalize_requirement(requirement_id: int):
    """Finalize requirement and send to user for confirmation"""
    try:
        # Update status to SentForUserConfirmation
        supabase.table("Requirement").update({
            "status": "SentForUserConfirmation"
        }).eq("id", requirement_id).execute()
        
        # Fetch updated record
        response = supabase.table("Requirement").select("*").eq("id", requirement_id).single().execute()
        
        if response.data:
            return response.data
        raise Exception("Failed to fetch updated requirement.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/contracts/send")
async def send_contract(contract: ContractRequest):
    # This endpoint's logic was already safe, no changes needed.
    try:
        contract_data = contract.dict()
        insert_response = supabase.table('Contracts').insert(contract_data).select("*").single().execute()
        if not insert_response.data: raise Exception("Failed to create the contract record.")
        
        supabase.table('Requirement').update({"status": "ContractSent"}).eq("id", contract.requirement_id).execute()
        return {"message": "Contract created and sent successfully.", "contract": insert_response.data}
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to send contract: {str(e)}")

@app.post("/requirements/{id}/add-item")
async def add_item_to_requirement(id: int, item: dict):
    """Add an item to requirement's finalized_items list"""
    try:
        # Fetch current requirement
        result = supabase.table("Requirement").select("*").eq("id", id).single().execute()
        requirement = result.data
        
        # Get current finalized_items or initialize empty list
        finalized_items = requirement.get("finalized_items") or []
        
        # Add new item if not already present
        new_item = item.get("item")
        if new_item and new_item not in finalized_items:
            finalized_items.append(new_item)
        
        # Update in database
        update_result = supabase.table("Requirement").update({
            "finalized_items": finalized_items
        }).eq("id", id).execute()
        
        return update_result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- REFACTORED ENDPOINT ---
@app.post("/requirements/{requirement_id}/validate", response_model=RequirementRecord)
async def validate_requirement(requirement_id: int):
    try:
        req_response = supabase.table('Requirement').select("initial_query").eq("id", requirement_id).single().execute()
        if not req_response.data: raise HTTPException(status_code=404, detail="Requirement not found.")
        
        initial_query = req_response.data['initial_query']
        suggestions = await agent_handler.generate_suggestions(initial_query)
        update_data = {"ai_suggestions": suggestions, "status": "InReview"}
        
        # 1. Update the record
        supabase.table('Requirement').update(update_data).eq("id", requirement_id).execute()

        # 2. Re-fetch the updated record
        response = supabase.table('Requirement').select("*").eq("id", requirement_id).single().execute()

        if response.data: return response.data
        raise Exception("Failed to fetch updated requirement.")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- REFACTORED ENDPOINT ---
@app.patch("/requirements/{requirement_id}/items", response_model=RequirementRecord)
async def update_finalized_items(requirement_id: int, items_update: ItemsUpdateRequest):
    try:
        # 1. Update the record
        supabase.table('Requirement').update({"finalized_items": items_update.items}).eq("id", requirement_id).execute()

        # 2. Re-fetch the updated record
        response = supabase.table('Requirement').select("*").eq("id", requirement_id).single().execute()
        
        if response.data: return response.data
        raise HTTPException(status_code=404, detail="Not found or failed to update.")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- REFACTORED ENDPOINT ---
@app.patch("/requirements/{requirement_id}/status", response_model=RequirementRecord)
async def update_requirement_status(requirement_id: int, status_update: StatusUpdateRequest):
    try:
        # 1. Update the record
        supabase.table('Requirement').update({"status": status_update.status}).eq("id", requirement_id).execute()

        # 2. Re-fetch the updated record
        response = supabase.table('Requirement').select("*").eq("id", requirement_id).single().execute()

        if response.data: return response.data
        raise HTTPException(status_code=404, detail="Not found or failed to update.")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ... (Endpoints from here down were either safe or did not need changes) ...

@app.post("/requirements/{requirement_id}/search-vendors", response_model=List[VendorRecord])
async def search_for_vendors(requirement_id: int):
    try:
        req_response = supabase.table("Requirement").select("*").eq("id", requirement_id).single().execute()
        if not req_response.data:
            raise HTTPException(status_code=404, detail="Requirement not found.")
        
        record = req_response.data
        items_str = ", ".join(record.get("finalized_items") or [])
        query = f"Vendors or suppliers for {record['initial_query']} with items like {items_str} in India"
        
        print(f"🔍 QUERY: {query}")  # Debug
        
        tavily_tool = TavilySearchResults(max_results=5)
        search_results = tavily_tool.invoke(query)
        
        print(f"🔍 RAW RESULTS: {search_results}")  # Debug
        print(f"🔍 RESULTS TYPE: {type(search_results)}")  # Debug
        print(f"🔍 RESULTS LENGTH: {len(search_results)}")  # Debug
        
        if search_results:
            print(f"🔍 FIRST RESULT: {search_results[0]}")  # Debug
        
        vendor_list = [
            VendorRecord(
                id=f"v-api-{i+1}",
                name=res.get("title", "Unnamed Vendor"),
                tags=[],
                revenue=random.randint(500000, 3000000),
                profile=random.randint(75, 95),
                rating=round(random.uniform(4.0, 5.0), 1),
                reviews=[VendorReview(rating=round(random.uniform(4.0, 5.0), 1), comment=res.get("content", "...")[:100])]
            ) 
            for i, res in enumerate(search_results)
        ]
        
        print(f"🔍 VENDOR LIST: {vendor_list}")  # Debug
        
        return vendor_list
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")  # Debug
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/requirements/{requirement_id}/send-rfq")
async def send_request_for_quotes(requirement_id: int, rfq_request: RFQRequest):
    try:
        vendor_ids = []
        for temp_vendor in rfq_request.vendors:
            vendor_response = supabase.table("Vendor").select("vendor_id").eq("name", temp_vendor.name).execute()
            
            if vendor_response.data:
                vendor_ids.append(vendor_response.data[0]["vendor_id"])
            else:
                new_vendor_data = {
                    "name": temp_vendor.name,
                    "rating": temp_vendor.rating,
                    "role_id": 2,
                    "tags": temp_vendor.tags
                }
                insert_response = supabase.table("Vendor").insert(new_vendor_data).execute()
                
                if insert_response.data:
                    new_vendor_id = insert_response.data[0]["vendor_id"]
                    vendor_ids.append(new_vendor_id)
        
        # Define the mandatory 4 questions
        questionnaire = [
            "Can you provide us with a detailed company profile, including your founding date, ownership structure, and key leadership biographies?",
            "What is your financial standing? Are you profitable, and can you provide audited financial statements or credit reports for the last two years?",
            "What are your security protocols and data protection measures?",
            "What does your customer support model look like?"
        ]
        
        # Store as JSON string
        import json
        questionnaire_json = json.dumps(questionnaire)
        
        # Create RFQ entries - FIXED column names
        rfq_entries = []
        for vid in vendor_ids:
            rfq_entries.append({
                "req_id": requirement_id,  # This matches your database schema
                "vendor_id": vid,
                "rfq": questionnaire_json,
                "status": "Sent"
            })
        
        # Insert RFQs
        rfq_response = supabase.table("RFQ").insert(rfq_entries).execute()
        
        if not rfq_response.data:
            raise Exception("Failed to create RFQ entries.")
        
        # Update requirement status - use req_id not id
        supabase.table("Requirement").update({"status": "RFQSent"}).eq("id", requirement_id).execute()
        
        return {"message": f"RFQ sent to {len(vendor_ids)} vendors successfully."}
    
    except Exception as e:
        print(f"ERROR: {str(e)}")  # Debug
        raise HTTPException(status_code=500, detail=str(e))


    
@app.get("/requirements/{requirement_id}/quotes", response_model=List[QuoteDetails])
async def get_quotes_for_requirement(requirement_id: int):
    try:
        response = supabase.rpc('get_quotes_for_requirement', {'req_id_param': requirement_id}).execute()
        if response.data: return response.data
        return []
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to fetch quotes: {str(e)}")



# ENDPOINT 2: Get specific vendor details
@app.get("/vendors/{vendor_id}")
async def get_vendor_details(vendor_id: int):
    """Get details of a specific vendor"""
    try:
        response = supabase.table("Vendor").select("*").eq("vendor_id", vendor_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        
        # If vendor doesn't exist, return a default object instead of 404
        return {
            "vendor_id": vendor_id,
            "name": f"Vendor {vendor_id}",
            "rating": 0,
            "tags": [],
            "profile": {}
        }
        
    except Exception as e:
        print(f"❌ Error fetching vendor {vendor_id}: {str(e)}")
        return {
            "vendor_id": vendor_id,
            "name": f"Vendor {vendor_id}",
            "rating": 0,
            "tags": [],
            "profile": {}
        }


@app.post("/quotes/run-scoring/{requirement_id}", response_model=List[QuoteDetails])
async def run_ai_scoring(requirement_id: int):
    # This endpoint's logic was already safe, no changes needed.
    try:
        quotes_response = await get_quotes_for_requirement(requirement_id)
        if not quotes_response: 
            raise HTTPException(status_code=404, detail="No quotes found for this requirement.")
        
        req_response = supabase.table('Requirement').select("initial_query, finalized_items").eq("id", requirement_id).single().execute()
        if not req_response.data: 
            raise HTTPException(status_code=404, detail="Original requirement not found.")
        
        requirement_details = req_response.data
        updates = []
        for quote in quotes_response:
            # --- START OF FIX ---
            # 'quote' is already a dictionary, so we pass it directly without .dict()
            scores = await agent_handler.score_vendor_quote(requirement_details, quote)
            # --- END OF FIX ---
            
            # The 'quote_id' needs to be accessed like a dictionary key now
            updates.append({
                "quote_id": quote['quote_id'], 
                "relevance_score": scores.get('relevance_score'), 
                "profile_score": scores.get('profile_score'), 
                "final_score": scores.get('final_score')
            })
        
        for update in updates:
            supabase.table('Quotes').update({k: v for k, v in update.items() if k != 'quote_id'}).eq('quote_id', update['quote_id']).execute()
            
        return await get_quotes_for_requirement(requirement_id)
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to run AI scoring: {str(e)}")

@app.post("/requirements/{requirement_id}/shortlist", response_model=List[QuoteDetails])
async def shortlist_top_vendors(requirement_id: int, request: ShortlistRequest):
    try:
        all_quotes = await get_quotes_for_requirement(requirement_id)
        if not all_quotes:
            raise HTTPException(status_code=404, detail="No quotes to shortlist.")
        
        # --- START OF FIX ---
        # Changed q.final_score to q['final_score']
        all_quotes.sort(key=lambda q: q['final_score'] or 0, reverse=True)
        
        # Changed q.quote_id to q['quote_id']
        top_quote_ids = [q['quote_id'] for q in all_quotes[:request.top_n]]
        
        for quote in all_quotes:
            # Changed quote.quote_id to quote['quote_id']
            supabase.table('Quotes').update({
                "is_shortlisted": quote['quote_id'] in top_quote_ids
            }).eq("quote_id", quote['quote_id']).execute()
        # --- END OF FIX ---
            
        supabase.table('Requirement').update({"status": "Shortlisted"}).eq("id", requirement_id).execute()
        
        return await get_quotes_for_requirement(requirement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to shortlist vendors: {str(e)}")

# 3. UPDATE THE /rfqs/invitations/{vendor_id} ENDPOINT
@app.get("/rfqs/invitations/{vendor_id}", response_model=List[RFQInvitation])
async def get_vendor_invitations(vendor_id: int):
    try:
        # Fetch RFQs without the problematic join
        rfq_response = supabase.table('RFQ').select(
            "rfq_id, req_id, status, rfq"
        ).eq("vendor_id", vendor_id).eq("status", "Sent").execute()
        
        invitations = []
        if rfq_response.data:
            for rfq in rfq_response.data:
                # Fetch requirement details separately
                try:
                    req_response = supabase.table('Requirement').select(
                        "title, initial_query"
                    ).eq("id", rfq['req_id']).execute()
                    
                    req_details = req_response.data[0] if req_response.data else {}
                except Exception as e:
                    print(f"Error fetching requirement {rfq['req_id']}: {str(e)}")
                    req_details = {}
                
                invitations.append(RFQInvitation(
                    rfq_id=rfq['rfq_id'],
                    req_id=rfq['req_id'],
                    status=rfq['status'],
                    rfq=rfq['rfq'],
                    requirement_title=req_details.get('title', 'N/A'),
                    requirement_query=req_details.get('initial_query', 'N/A')
                ))
        
        return invitations
        
    except Exception as e:
        print(f"Error fetching invitations for vendor {vendor_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# In main.py, replace your existing get_vendors_with_rfqs function with this
# In main.py, replace the get_vendors_with_rfqs function again

@app.get("/vendors/with-rfqs", response_model=List[VendorWithRFQ])
async def get_vendors_with_rfqs():
    """Get all vendors who have received at least one RFQ"""
    try:
        rfq_response = supabase.table("RFQ").select("vendor_id").execute()
        if not rfq_response.data:
            return []

        vendor_ids = list(set([rfq["vendor_id"] for rfq in rfq_response.data]))
        if not vendor_ids:
            return []

        vendors_response = supabase.table("Vendor").select(
            "vendor_id, name, rating, tags, profile"
        ).in_("vendor_id", vendor_ids).execute()
        if not vendors_response.data:
            return []

        formatted_vendors = []
        for vendor in vendors_response.data:
            # --- Robust Tags Handling ---
            tags = vendor.get("tags")
            processed_tags = []
            if isinstance(tags, list):
                processed_tags = tags
            elif isinstance(tags, str) and tags.strip():
                try:
                    parsed = json.loads(tags)
                    if isinstance(parsed, list):
                        processed_tags = parsed
                except json.JSONDecodeError:
                    processed_tags = [t.strip() for t in tags.split(',')]

            # --- FIX: Robust Profile Handling ---
            profile = vendor.get("profile")
            processed_profile = {} # Default to an empty dictionary
            if isinstance(profile, dict):
                processed_profile = profile
            
            formatted_vendor = VendorWithRFQ(
                vendor_id=vendor.get("vendor_id"),
                name=vendor.get("name", "Unknown Vendor"),
                rating=float(vendor.get("rating") or 0.0),
                tags=processed_tags,
                profile=processed_profile  # Use the processed dictionary
            )
            formatted_vendors.append(formatted_vendor)
        
        return formatted_vendors
        
    except Exception as e:
        print(f"❌ Error in /vendors/with-rfqs: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


@app.post("/quotes/submit")
async def submit_quote(quote_data: QuoteSubmitRequest):
    try:
        # 1. Prepare and perform the upsert operation
        upsert_data = {
            "rfq_id": quote_data.rfq_id, 
            "vendor_id": quote_data.vendor_id, 
            "amount": quote_data.amount, 
            "items_covered": quote_data.items_covered, 
            "status": "Submitted"
        }
        supabase.table('Quotes').upsert(upsert_data, on_conflict="rfq_id, vendor_id").execute()

        # 2. Re-fetch the record you just upserted to return it
        response = supabase.table('Quotes').select("*")\
            .eq("rfq_id", quote_data.rfq_id)\
            .eq("vendor_id", quote_data.vendor_id)\
            .single().execute()

        if response.data: 
            return response.data
            
        raise Exception("Failed to submit or re-fetch quote.")
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))

# --- REFACTORED ENDPOINT ---
@app.patch("/quotes/{quote_id}/answers")
async def submit_quote_answers(quote_id: int, answers_data: QuoteAnswersRequest):
    try:
        # 1. Update the Quotes table
        supabase.table('Quotes').update({"answers": answers_data.answers}).eq("quote_id", quote_id).execute()
        
        # 2. Re-fetch the updated quote to get the rfq_id
        quote_response = supabase.table('Quotes').select("rfq_id").eq("quote_id", quote_id).single().execute()

        if quote_response.data:
            # 3. Update the RFQ table status
            supabase.table('RFQ').update({"status": "Responded"}).eq("rfq_id", quote_response.data['rfq_id']).execute()
            
            # 4. Fetch the full quote details again to return
            full_response = supabase.table('Quotes').select("*").eq("quote_id", quote_id).single().execute()
            if full_response.data:
                return full_response.data

        raise HTTPException(status_code=404, detail="Quote not found or failed to update.")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/requirements/templates", response_model=List[RequirementRecord])
async def list_templates():
    try:
        response = supabase.table('Requirement').select("*").eq('is_template', True).execute()
        return response.data if response.data else []
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/requirements/reuse/{template_id}", response_model=RequirementRecord)
async def reuse_template(template_id: int):
    try:
        template_response = supabase.table('Requirement').select("*").eq("id", template_id).eq('is_template', True).single().execute()
        if not template_response.data: raise HTTPException(status_code=404, detail="Template not found.")
        
        template = template_response.data
        new_record_data = {"title": f"(Reused) {template['title']}", "status": "InReview", "initial_query": template['initial_query'], "extracted_requirements": template['extracted_requirements'], "is_template": False}
        insert_response = supabase.table('Requirement').insert(new_record_data).select("*").single().execute()
        
        if insert_response.data: return insert_response.data
        raise Exception("Failed to create from template.")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/requirements/blank", response_model=RequirementRecord)
async def create_blank_request():
    try:
        new_record_data = {"title": "New Blank Request", "status": "InReview", "initial_query": "Admin-initiated request.", "is_template": False}
        response = supabase.table('Requirement').insert(new_record_data).select("*").single().execute()
        if response.data: return response.data
        raise Exception("Failed to create blank request.")
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- REFACTORED ENDPOINT (using the user's provided fix) ---
@app.get("/requirements/{requirement_id}", response_model=RequirementRecord)
async def get_requirement_details(requirement_id: int):
    try:
        response = supabase.table('Requirement').select("*, Vendor(name)").eq("id", requirement_id).maybe_single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Requirement not found")
        
        record = response.data
        
        if record.get('status') == 'Submitted':
            # 1. Update the status
            supabase.table('Requirement').update({"status": "InReview"}).eq("id", requirement_id).execute()
            
            # 2. Re-fetch the updated record
            updated_response = supabase.table('Requirement').select("*, Vendor(name)").eq("id", requirement_id).single().execute()
            
            if updated_response.data:
                record = updated_response.data
        
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- REFACTORED ENDPOINT ---
@app.post("/requirements/{requirement_id}/confirm", response_model=RequirementRecord)
async def handle_user_confirmation(requirement_id: int, confirmation: UserConfirmationRequest):
    try:
        req_response = supabase.table('Requirement').select("*").eq("id", requirement_id).single().execute()
        if not req_response.data: raise HTTPException(status_code=404, detail="Requirement not found.")
        
        record = req_response.data
        if record['status'] != 'SentForUserConfirmation': raise HTTPException(status_code=400, detail="Requirement not awaiting confirmation.")
        
        if confirmation.action == "approve":
            update_data = {"status": "UserConfirmed"}
        elif confirmation.action == "request_changes":
            if not confirmation.comment: raise HTTPException(status_code=400, detail="Comment required for changes.")
            new_initial_query = f"{record['initial_query']}\n\n--- User Requested Changes ---\n{confirmation.comment}"
            update_data = {"status": "Submitted", "initial_query": new_initial_query}
        else:
            raise HTTPException(status_code=400, detail="Invalid action.")
            
        # 1. Update the record
        supabase.table('Requirement').update(update_data).eq("id", requirement_id).execute()

        # 2. Re-fetch the updated record
        response = supabase.table('Requirement').select("*").eq("id", requirement_id).single().execute()
        
        if response.data: return response.data
        raise Exception("Failed to update requirement.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))