from model_utils import *
import json
import asyncio

def build_prompt(model_id):
    if model_id == 1:
        model_name = "Echo"
    elif model_id == 2:
        model_name = "Lele"
    elif model_id == 3: 
        model_name = "Neko"
    else:
        model_name = "Unknown"
    
    return f"""
    你是AI助手{model_name}。请根据当前对话情况，用JSON格式决定你的行为：
    {{
        "should_respond": true/false,
        "target_model": "model_name或null",
        "response_type": "question/statement/observation",
        "content": "你的回复内容"
    }}
    """

async def get_llm_response(prompt):
    return await chat(prompt) 

class AutonomousDiscussion:
    def __init__(self):
        self.models = [1, 2, 3]
        self.conversation_history = []
        
    async def get_model_decision(self, model_id, context):
        prompt = build_prompt(model_id) + f"\n当前对话上下文：{context}"
        response = await get_llm_response(prompt)
        
        try:
            decision = json.loads(response)
            return decision
        except json.JSONDecodeError:
            return {"should_respond": False, "target_model": None, "response_type": "pass", "content": ""}
    
    async def run_discussion_round(self):
        context = "\n".join(self.conversation_history[-5:])  # Last 5 messages as context
        
        for model_id in self.models:
            decision = await self.get_model_decision(model_id, context)
            
            if decision.get("should_respond", False):
                model_name = ["", "Echo", "Lele", "Neko"][model_id]
                message = f"{model_name}: {decision.get('content', '')}"
                self.conversation_history.append(message)
                print(message)
    
    async def start_discussion(self, rounds=10):
        print("开始自主讨论...")
        for round_num in range(rounds):
            print(f"\n--- Round {round_num + 1} ---")
            await self.run_discussion_round()
            
            if not any(self.conversation_history[-3:]):
                print("讨论自然结束")
                break

# Usage
async def main():
    discussion = AutonomousDiscussion()
    await discussion.start_discussion()

# Run the discussion
asyncio.run(main())
