from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import openai, silero

from agent.config import settings
from agent.journal_tool import log_daily_reflection
from agent.prompts import SYSTEM_PROMPT
from agent.rag import LumaRetriever

load_dotenv()

class ReflectFunctionContext(llm.FunctionContext):
    def __init__(self, retriever: LumaRetriever) -> None:
        super().__init__()
        self.retriever = retriever

    @llm.ai_callable(
        name="search_fitness_journal",
        description="Search past days in the fitness journal PDF to answer questions or compare today's stats to history.",
    )
    async def search_fitness_journal(
        self,
        query: Annotated[
            str,
            llm.TypeInfo(description="The natural-language question mapping to the historical daily logs."),
        ],
    ) -> str:
        context = await self.retriever.search_as_context(query)
        if context:
            return context
        return "No historical logs found for that question."

    @llm.ai_callable(
        name="log_daily_reflection",
        description="Append the user's daily stats and notes to the persistent markdown file and auto-update the RAG store.",
    )
    async def log_daily_reflection(
        self,
        date: Annotated[str, llm.TypeInfo(description="The date or 'Day X' label for today like 'March 26th'")],
        steps: Annotated[int, llm.TypeInfo(description="Total steps taken today")],
        calories: Annotated[int, llm.TypeInfo(description="Total kcal consumed today")],
        protein: Annotated[int, llm.TypeInfo(description="Total protein grams hit")],
        notes: Annotated[str, llm.TypeInfo(description="A short 1-sentence recap of the workout and mood")],
    ) -> str:
        return log_daily_reflection(
            date=date,
            steps=steps,
            calories=calories,
            protein=protein,
            notes=notes,
        )

def prewarm(proc) -> None:
    proc.userdata["retriever"] = LumaRetriever()
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()

    retriever: LumaRetriever = ctx.proc.userdata["retriever"]
    vad = ctx.proc.userdata["vad"]
    fnc_ctx = ReflectFunctionContext(retriever=retriever)
    chat_ctx = llm.ChatContext(
        messages=[llm.ChatMessage.create(text=SYSTEM_PROMPT, role="system")]
    )

    assistant = VoicePipelineAgent(
        vad=vad,
        stt=openai.STT(model=settings.stt_model),
        llm=openai.LLM(model=settings.chat_model),
        tts=openai.TTS(voice=settings.tts_voice),
        chat_ctx=chat_ctx,
        fnc_ctx=fnc_ctx,
    )

    assistant.start(ctx.room, participant)
    await assistant.say(
        (
            "Hey Yogya. Ready to log your day? Walk me through your steps, your meals, and how your workout went."
        ),
        allow_interruptions=True,
    )

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
