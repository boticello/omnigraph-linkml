"""Manually curated TA1044 mortality branch; summaries are paraphrases.

No source text, patient data or numerical analysis is reproduced. See
docs/example-ta1044.md for provenance, curation limits and edition uncertainty.
"""

DISCUSSION_URL = "https://www.nice.org.uk/guidance/ta1044/chapter/3-Committee-discussion"
PAPERS_URL = "https://www.nice.org.uk/guidance/ta1044/documents/committee-papers-2"


def node(kind, **data):
    return {"type": kind, "data": data}


def edge(kind, identity, source, target, **data):
    return {"edge": kind, "id": identity, "from": source, "to": target, "data": data}


def records():
    """Return fresh records so failure probes cannot modify the curated corpus."""
    nodes = [
        node("Recommendation", recommendation_id="TA1044-R1", label="TA1044 recommendation 1.1",
             url="https://www.nice.org.uk/guidance/ta1044/chapter/1-Recommendations",
             scope="Standard-care mortality contribution only; incomplete recommendation justification"),
        node("Passage", passage_id="discussion-3-28", label="Recommendation conclusion",
             url=DISCUSSION_URL + "#recommendation", locator="TA1044 section 3.28",
             summary="Managed access addresses remaining uncertainty; preferred assumptions are referenced."),
        node("Passage", passage_id="discussion-3-26", label="Preferred assumptions",
             url=DISCUSSION_URL + "#committees-preferred-assumptions", locator="TA1044 section 3.26",
             summary="The committee lists its preferred standard-care mortality assumption."),
        node("Passage", passage_id="discussion-3-8", label="Standard-care mortality discussion",
             url=DISCUSSION_URL + "#standard-care-mortality-modelling", locator="TA1044 section 3.8",
             summary="Competing mortality analyses are compared; further validation is needed."),
        node("Passage", passage_id="papers-393", label="EAG scenario assumptions",
             url=PAPERS_URL + "#page=393", locator="Committee papers PDF p.393; report p.69, Table 15",
             pdf_page=393, summary="The scenario assumptions identify company mortality inputs as Desai/ICER."),
        node("Passage", passage_id="papers-408", label="EAG mortality critique",
             url=PAPERS_URL + "#page=408", locator="Committee papers PDF p.408; report p.84, Issue 3",
             pdf_page=408, summary="Jiao is used to challenge an argument about absent older-patient data."),
        node("Analysis", analysis_id="company-mortality", label="Company standard-care mortality analysis",
             url=PAPERS_URL + "#page=393", author="Company",
             context="Company inputs preferred in published discussion; later EAG scenario Table 15"),
        node("Analysis", analysis_id="eag-earlier-base-case", label="EAG alternative mortality base case",
             url=DISCUSSION_URL + "#standard-care-mortality-modelling", author="EAG",
             context="Alternative base case described in section 3.8; not the later company-input scenario"),
        node("Analysis", analysis_id="eag-mortality-critique", label="EAG critique of mortality validation",
             url=PAPERS_URL + "#page=408", author="EAG",
             context="Later report Issue 3; distinct from the earlier EAG base case"),
        node("SourceDocument", document_id="desai-2020", label="Desai et al. (2020)",
             url="https://doi.org/10.1007/s00277-020-04233-w",
             citation_key="doi:10.1007/s00277-020-04233-w", document_kind="journal-article",
             identification="Matched author, year and title to PMID 32869184"),
        node("SourceDocument", document_id="jiao-2023", label="Jiao et al. (2023)",
             url="https://doi.org/10.1182/bloodadvances.2022009202",
             citation_key="doi:10.1182/bloodadvances.2022009202", document_kind="journal-article",
             identification="Matched author, year and title to PMID 36929166"),
        node("SourceDocument", document_id="icer-2023", label="ICER SCD report (2023), edition unresolved",
             url="https://icer.org/assessment/sickle-cell-disease-2023/",
             citation_key="icer:scd-2023-report-family", document_kind="report-family",
             identification="Report family named by NICE; exact edition not established"),
    ]
    links = [
        edge("RecommendationDiscussion", "recommendation-discussion", "TA1044-R1", "discussion-3-28",
             basis="Curated correspondence: section 3.28 restates recommendation 1.1"),
        edge("DiscussionReference", "conclusion-assumptions", "discussion-3-28", "discussion-3-26",
             basis="Explicit section reference in 3.28"),
        edge("DiscussionReference", "assumptions-mortality", "discussion-3-26", "discussion-3-8",
             basis="Explicit section reference in 3.26 mortality assumption"),
        edge("DiscussionAnalysis", "company-preferred", "discussion-3-8", "company-mortality",
             stance="preferred", attributed_to="Committee",
             summary="Company mortality inputs preferred as more representative; further validation needed."),
        edge("DiscussionAnalysis", "company-questioned", "discussion-3-8", "company-mortality",
             stance="questioned", attributed_to="EAG",
             summary="The EAG questioned the relevance of a younger source population."),
        edge("DiscussionAnalysis", "eag-alternative", "discussion-3-8", "eag-earlier-base-case",
             stance="alternative", attributed_to="EAG",
             summary="Jiao mortality rates were used in an alternative base case."),
        edge("DiscussionAnalysis", "eag-questioned", "discussion-3-8", "eag-earlier-base-case",
             stance="questioned", attributed_to="Company and clinical experts",
             summary="Whole-SCD data were questioned for severe SCD; the company considered Jiao unsuitable for decision making."),
    ]
    uses = [
        ("use-company-desai", "company-mortality", "desai-2020", "papers-393", "mortality-input",
         "Table 15 explicitly identifies Desai/ICER; 3.8 also names both sources."),
        ("use-company-icer", "company-mortality", "icer-2023", "papers-393", "mortality-input",
         "The ICER report family is identified; edition remains unresolved."),
        ("use-eag-jiao", "eag-earlier-base-case", "jiao-2023", "discussion-3-8", "mortality-input",
         "Section 3.8 identifies Jiao as the source of the EAG base-case mortality rates."),
        ("use-eag-jiao-critique", "eag-mortality-critique", "jiao-2023", "papers-408", "challenge",
         "Jiao includes older cohorts and is used to rebut the missing-older-patients argument."),
    ]
    for identity, analysis, source, passage, purpose, summary in uses:
        nodes.append(node("EvidenceUse", evidence_use_id=identity, purpose=purpose,
                          basis="Explicit source use in documenting passage", summary=summary))
        for role, target in [("Analysis", analysis), ("Source", source), ("Passage", passage)]:
            links.append(edge("EvidenceUse" + role, identity + "-" + role.lower(), identity, target))
    return nodes + links
