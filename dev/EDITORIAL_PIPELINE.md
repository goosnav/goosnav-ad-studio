# Editorial upgrade (new runs)

The new story and edit pipeline addresses nonsensical dialogue and awkward pauses without requiring more character motion. Existing Goosnav character rigs are canonical, including the characters featured in the two example videos.

Pipeline: research -> three-script contest -> independent story_sense -> director -> storyboard -> measured speech/audio -> animation preview -> director review -> independent edit_plan -> final editor conform -> independent edit_review -> Goosnav Frame CTA -> technical QA (using EDITED timestamps) -> creative QA -> packaging.

The script-sense reviewer traces each selected ad as setup, cause, response, payoff, product connection. It is permitted to reject the entire selection and return to writing. A technically renderable script is not necessarily an intelligible script.

The editor watches the actual preview with sound and writes a chronological edit decision list. Example: first clip 0-2.5 s, second 3.2-7.5 s, third 7.5-10 s. The middle cut removes 0.7 s of dead air. The protected final interval is the clean product hero for Goosnav Frame. All retained lines must be complete; any omitted lines must be identified and justified.

The final editor renders the original scene at full resolution and uses the deterministic helper to cut video and mixed audio simultaneously. To conform a scene:

    PYTHONPATH=/absolute/path/to/repo python3 -m harness.editing --video source-render.mp4 --audio source-mix.wav --plan edit-plan.json --timeline source-timeline.json --config run-config.json --direction direction.json --output master.mp4 --output-timeline edited-timeline.json

All JSON inputs must be copies of accepted run inputs. Edited transcript timings are not estimated; they are recalculated by the helper from measured sample positions and validated at the edit contract and final technical QA. Custom effects/music should be mixed against original source time first, then conformed with picture. Keep dialogue clear. Silence must be earned; music is optional.

A static two-character scene can be good. The acceptance criteria concern comprehensible replies, coherent setup/payoff, clean timing, and purposeful sound, not unnecessary walking, gestures or props. If the editor cannot repair meaning, the independent cut reviewer sends the appropriate upstream stage back to work.

The upgrade affects new runs only. Stored in-progress runs preserve their old task graphs. No ad iteration needs to be generated merely to install or test the changes.
