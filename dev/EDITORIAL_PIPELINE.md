# Lean editorial pipeline (new runs only)

Campaign stages: **research -> write -> select**. Research is a brief fact extraction (0-2 sources). Writing produces two candidates/ad. Selection is a combined causal-coherence review: choose strong stories, or reject all and return to writing.

Production stages per ad: **direct -> assets -> audio -> animate -> edit -> frame -> qa -> creative_qa -> package**.

There are three campaign LLM calls and six LLM calls per ad in the normal no-repair path. Previously there were seven campaign LLM stages and ten LLM stages per ad. The remaining deterministic tasks still enforce media integrity. Model routing favors economy for research, balanced for scripts/directing/editorial work, economy for final review, and retains a heavy high-quality animator. Lightweight sessions have limited retries and short deadlines.

The dedicated editor inspects the preview, creates a source-time EDL and executes it in one session. It returns plan, master and edited timeline. The existing harness.editing helper cuts original video and source-time audio together and rebases speech timestamps. Frame, dialogue/audio checks, picture checks and loudness/ASR QA remain deterministic.

Prompt inputs are scoped by stage: no replay of the entire accepted run, repeated script pools, worker routing configuration or unrelated source metadata. Previous-run browsing is no longer a default research task.

Character rigs are unchanged. A static two-character scene is acceptable when the dialogue and timing are good. The selection check rejects non sequiturs; final creative QA can still request targeted repairs.

Existing in-progress runs preserve their stored task graph. To use the lean default, begin a new run. No ad generation is required for installing these code changes. Token/dollar savings are expected structurally but must be measured in real usage.
