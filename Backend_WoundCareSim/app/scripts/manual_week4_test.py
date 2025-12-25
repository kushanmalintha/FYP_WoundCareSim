import asyncio
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.agents.communication_agent import CommunicationAgent
from app.agents.clinical_agent import ClinicalAgent
from app.agents.knowledge_agent import KnowledgeAgent

async def run_week4_test():
    scenario_id = "scenario_test_001"
    step = "HISTORY"
    transcript = "Hello, I am a nursing student. May I confirm your name and explain the wound care procedure?"

    print("--- Starting Test ---")
    
    coordinator = Coordinator()
    evaluation_service = EvaluationService(coordinator=coordinator)

    # 1. Prepare Context
    try:
        context = await evaluation_service.prepare_agent_context(
            transcript=transcript,
            scenario_id=scenario_id,
            step=step,
            system_instruction="Evaluate nursing student performance."
        )
        print("Context Prepared")
    except Exception as e:
        print(f"Context Preparation Failed: {e}")
        return

    # 2. Initialize Agents
    agents = [
        CommunicationAgent(),
        ClinicalAgent(),
        KnowledgeAgent()
    ]

    evaluator_outputs = []

    print(f"--- Running {len(agents)} Agents ---")

    for agent in agents:
        print(f"   > Running {agent.__class__.__name__}...")
        try:
            # The agent now handles the JSON parsing internally
            result = await agent.evaluate(
                current_step=context["step"],
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
            evaluator_outputs.append(result)
            print(f"     Success. Confidence: {result.confidence}")
        except Exception as e:
            print(f"     Agent Failed: {e}")

    # 3. Aggregate
    print("--- Aggregating Results ---")
    aggregated = await evaluation_service.aggregate_evaluations(
        evaluator_outputs=evaluator_outputs,
        step=step
    )

    print("\n=== WEEK-4 EVALUATION RESULT ===\n")
    print(aggregated)

if __name__ == "__main__":
    asyncio.run(run_week4_test())
