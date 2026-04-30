"""Prompt templates for the web research agent.

Template bodies are stubs — refine once the pipeline runs end-to-end and
the team agrees on what research outputs are most useful.
"""


def build_research_prompt(
    project_name: str,
    project_id: str,
    municipality: str,
    state: str,
) -> str:
    """Build the web research prompt for a given project.

    Args:
        project_name: Human-readable project name.
        project_id: Project UUID (included for specificity in searches).
        municipality: Resolved municipality name.
        state: Resolved state abbreviation or full name.

    Returns:
        Filled prompt string ready to send to the Anthropic API.
    """
    return _PROJECT_RESEARCH_TEMPLATE.format(
        project_name=project_name,
        project_id=project_id,
        municipality=municipality or "unknown",
        state=state or "unknown",
    )


# TODO: Refine this prompt once the pipeline runs end-to-end and the team
#       reviews the quality of web research results. Consider breaking into
#       sub-prompts per research category (permits, utility owners, blueprints).
_PROJECT_RESEARCH_TEMPLATE = """
You are a research assistant for a geospatial infrastructure company.

Research the following construction/infrastructure project:

  Project Name: {project_name}
  Project ID:   {project_id}
  Location:     {municipality}, {state}

Search for:
1. Public permits, filings, or regulatory records related to this project or area.
2. Utility owner information for this area (gas, electric, water, telecom companies).
3. Publicly available blueprints, engineering drawings, or technical documents.
4. Any environmental or infrastructure impact records for the project area.

Synthesize your findings into a clear summary paragraph. List every source URL you used.
For each source, note why it is relevant to this project.
""".strip()