import os
import traceback

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class SupportAgent:

    def __init__(self, kb):
        self.kb = kb

        self.api_key = os.getenv(
            "GEMINI_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        ).strip()

        print("========================================")
        print("SUPPORTFLOW AI - GEMINI CONFIG")
        print("Configured:", bool(self.api_key))
        print("Model:", self.model)
        print("========================================")

        if self.api_key:
            try:
                self.client = genai.Client(
                    api_key=self.api_key
                )

                print(
                    "GEMINI CLIENT: initialized successfully"
                )

            except Exception as e:
                print(
                    "GEMINI CLIENT ERROR:",
                    repr(e)
                )
                traceback.print_exc()
                self.client = None

        else:
            print(
                "GEMINI CLIENT: API key is missing"
            )
            self.client = None


    def answer(self, message, analysis):

        if not self.client:
            print(
                "GEMINI ERROR: client is not configured"
            )

            return (
                "The AI service is not configured right now. "
                "Please contact the administrator."
            )


        # ================================================
        # RAG
        # ================================================

        try:
            hits = self.kb.search(
                message,
                top_k=4
            )

            print(
                "RAG STEP: retrieved",
                len(hits),
                "knowledge chunks"
            )

        except Exception as e:
            print(
                "RAG ERROR:",
                repr(e)
            )

            traceback.print_exc()

            hits = []


        context_parts = []

        for hit in hits:

            text = hit.get(
                "text",
                ""
            )

            if text:
                context_parts.append(
                    f"VERIFIED KNOWLEDGE:\n{text}"
                )


        context = "\n\n".join(
            context_parts
        )


        if not context.strip():
            context = (
                "No relevant information was found "
                "in the verified knowledge base."
            )


        # ================================================
        # SYSTEM INSTRUCTION
        # ================================================

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
   or technical RAG information to the customer.

6. Answer naturally and professionally.

7. Keep the answer concise unless the
   customer asks for details.

8. Return only the customer-facing answer.
"""


        # ================================================
        # USER PROMPT
        # ================================================

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


        # ================================================
        # GEMINI
        # ================================================

        try:

            print("========================================")
            print("GEMINI STEP 1: sending request")
            print("GEMINI MODEL:", self.model)
            print("========================================")


            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    max_output_tokens=500,
                ),
            )


            print(
                "GEMINI STEP 2: response received"
            )

            print(
                "GEMINI RESPONSE TYPE:",
                type(response).__name__
            )


            if response is None:

                print(
                    "GEMINI ERROR: response is None"
                )

                return (
                    "The AI service returned an empty response. "
                    "Please try again."
                )


            answer = getattr(
                response,
                "text",
                None
            )


            if answer:
                answer = answer.strip()


            if answer:

                print(
                    "GEMINI STEP 3: answer generated successfully"
                )

                print(
                    "ANSWER LENGTH:",
                    len(answer)
                )

                return answer


            # ============================================
            # EMPTY RESPONSE
            # ============================================

            print("========================================")
            print(
                "GEMINI ERROR: response.text is empty"
            )

            print(
                "GEMINI RESPONSE:",
                repr(response)
            )


            candidates = getattr(
                response,
                "candidates",
                None
            )

            print(
                "GEMINI CANDIDATES:",
                repr(candidates)
            )


            prompt_feedback = getattr(
                response,
                "prompt_feedback",
                None
            )

            print(
                "GEMINI PROMPT FEEDBACK:",
                repr(prompt_feedback)
            )

            print("========================================")


            return (
                "The AI service could not generate "
                "a response right now. Please try again."
            )


        except Exception as e:

            print("========================================")
            print("GEMINI API ERROR:")
            print(repr(e))

            print("ERROR TYPE:")
            print(type(e).__name__)

            print("ERROR STRING:")
            print(str(e))

            print("FULL TRACEBACK:")
            traceback.print_exc()

            print("========================================")


            return (
                "The AI service is temporarily unavailable. "
                "Please try again in a moment."
            )