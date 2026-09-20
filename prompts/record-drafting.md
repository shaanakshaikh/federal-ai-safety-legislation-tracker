# Record drafting prompt

Draft a canonical record only from the supplied official-source extracts and the repository schema. Cite every material claim using the exact supplied `source_id`. Preserve uncertainty rather than infer missing facts.

The output must include `agent_confidence`, `agent_flags`, and `requires_human_review: true`. Never change inclusion criteria, delete an existing record, replace an official link with secondary reporting, or claim that a proposal is enacted, vetoed, inactive, or dead without direct official evidence. Do not rewrite committee-dynamics analysis automatically.
