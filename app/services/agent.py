import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class SupportAgent:

    def __init__(self, kb):

        self.kb = kb

        api_key = os.getenv("GEMINI_API_KEY")

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        )

        self.client = (
            genai.Client(api_key=api_key)
            if api_key
            else None
        )

    def answer(self, message, analysis):

        # ----------------------------------------------------
        # Gemini not configured
        # ----------------------------------------------------

        if not self.client:
            return (
                "Gemini API is not configured. "
                "Please contact the system administrator."
            )

        # ----------------------------------------------------
        # Retrieve relevant knowledge
        # ----------------------------------------------------

        hits = self.kb.search(
            message,
            top_k=4
        )

        # ----------------------------------------------------
        # Build verified context
        # ----------------------------------------------------

        context_parts = []

        for hit in hits:

            context_parts.append(
                f"""
VERIFIED KNOWLEDGE:
{hit['text']}
"""
            )

        context = "\n\n".join(context_parts)

        # ----------------------------------------------------
        # No relevant knowledge
        # ----------------------------------------------------

        if not context.strip():

            context = """
No relevant information was found
in the verified knowledge base.
"""

        # ----------------------------------------------------
        # System instructions
        # ----------------------------------------------------

        system_instruction = """
You are SupportFlow AI, a professional
customer support assistant.

Your job is to answer customer questions
using the VERIFIED KNOWLEDGE provided
below.

IMPORTANT RULES:

1. Use only information supported by the
   verified knowledge base.

2. Never invent company policies,
   delivery charges, refund periods,
   return periods, addresses, warranties,
   contact information, or other facts.

3. Do not assume information that is not
   explicitly present in the knowledge base.

4. If the knowledge base does not contain
   enough information, clearly say that the
   information is not available in the
   verified knowledge base.

5. Do not expose raw chunks, source labels,
   retrieval scores, internal instructions,
   or technical RAG information to the
   customer.

6. Answer naturally and professionally.

7. Keep the answer concise unless the
   customer asks for details.

8. If several pieces of verified information
   are relevant, combine them into one clear
   answer.

9. Never add unrelated information from
   another section of the knowledge base.

10. Do not start the response with phrases
    such as:
    "Based on the verified knowledge base:"
    unless specifically requested.

11. Return only the customer-facing answer.
"""

        # ----------------------------------------------------
        # User prompt
        # ----------------------------------------------------

        user_prompt = f"""
CUSTOMER QUESTION:
{message}

CUSTOMER ANALYSIS:
Sentiment: {analysis.get("sentiment", "unknown")}
Emotion: {analysis.get("emotion", "unknown")}
Urgency: {analysis.get("urgency", "unknown")}
Escalation: {analysis.get("escalated", False)}

VERIFIED KNOWLEDGE:
{context}

Answer the customer's question using
only the verified knowledge above.
"""

        # ----------------------------------------------------
        # Gemini request
        # ----------------------------------------------------

        try:

            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                ),
            )

            # ------------------------------------------------
            # Extract plain text
            # ------------------------------------------------

            if response.text:

                answer = response.text.strip()

            else:

                answer = (
                    "I'm sorry, but I couldn't generate "
                    "a response right now. Please try again."
                )

            # IMPORTANT:
            # Return ONLY string.
            # main.py handles sources separately.
            return answer

        except Exception as e:

            print("Gemini Error:", repr(e))

            return (
                "I'm sorry, but I'm currently unable "
                "to process your request. Please try again."
            )