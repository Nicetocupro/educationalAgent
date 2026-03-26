from langchain.messages import SystemMessage, AIMessage
from agent.states import State
from pydantic import BaseModel, Field

class PhoneNumberExtraction(BaseModel):
    """Schema for parsing user-provided account information."""
    phone_number: str = Field(description = "The user's phone number")


class VerifyInfoAgent:
    def __init__(self, model):
        self.model = model
        self.structured_llm = model.with_structured_output(schema=PhoneNumberExtraction)

        self.structured_system_prompt = """You are a customer service representative responsible for extracting the customer's phone number.\n 
                                    Only extract the customer's account information from the message history. 
                                    If they haven't provided the information yet, return an empty string for the file"""
        
    def __call__(self, state:State):
        if state.get("customer_id") is not None:
            return
        else:
            user_input = state["messages"][-1]
            parsed_info = self.structured_llm.invoke([SystemMessage(content=self.structured_system_prompt)] + [user_input])

            identifier = parsed_info.phone_number

            customer_id = ""
        if (identifier):

            customer_id = 1
            """
            这是找到验证码，通过手机的验证码去得到customer_id
            # We have the phone number, find the customer record
            query = f"SELECT CustomerId FROM Customer WHERE Phone = '{identifier}';"
            result = db.run(query)
            # Add error handling for empty or invalid results
            try:
                formatted_result = ast.literal_eval(result)
                if formatted_result:
                    customer_id = formatted_result[0][0]
            except (ValueError, SyntaxError):
                # Query returned no results or invalid format
                pass
                
            """
        if customer_id != "":
            intent_message = AIMessage(
                content= f"Thank you for providing your information! I was able to verify your account with customer id {customer_id}."
            )
            return {
                  "customer_id": customer_id,
                  "messages" : [intent_message]
                  }
        
        else:
            system_instructions = """
            You are a music store agent, where you are trying to verify the customer identity as the first step of the customer support process. 
            You cannot support them until their account is verified. 
            In order to verify their identity, identify the phone number they have provied. 
            If the customer has not provided their phone number, please ask them for it.
            If they have provided the phone number but their record cannot be found, please ask them to revise it.

            IMPORTANT: Do NOT ask any questions about their request, or make any attempt at addressing their request until their identity is verified. It is CRITICAL that you only ask about their identity for security purposes.
            """
            response = self.model.invoke([SystemMessage(content=system_instructions)]+state['messages'])
            return {"messages": [response]}