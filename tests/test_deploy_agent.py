"""Offline tests for the agent spec and deploy SQL."""

import yaml

import deploy_agent


def test_spec_renders_for_each_environment():
    for env, db in (("dev", "NOI_DEV"), ("prod", "NOI_PROD")):
        spec = yaml.safe_load(deploy_agent.render_spec(env))
        assert spec["tool_resources"]["NetworkMetrics"]["semantic_view"] == f"{db}.SEMANTIC.NETWORK_OPS_ANALYTICS"
        assert spec["tool_resources"]["KnowledgeBase"]["name"] == f"{db}.SEARCH.SUPPORT_DOCS"


def test_every_tool_has_resources_and_analyst_has_execution_environment():
    spec = yaml.safe_load(deploy_agent.render_spec("dev"))
    names = {t["tool_spec"]["name"] for t in spec["tools"]}
    assert names == set(spec["tool_resources"])
    assert spec["tool_resources"]["NetworkMetrics"]["execution_environment"]["type"] == "warehouse"


def test_search_tools_split_articles_from_cases():
    res = yaml.safe_load(deploy_agent.render_spec("dev"))["tool_resources"]
    assert res["CaseHistory"]["filter"] == {"@eq": {"doc_type": "support_case"}}
    kb_types = {c["@eq"]["doc_type"] for c in res["KnowledgeBase"]["filter"]["@or"]}
    assert kb_types == {"kb_article", "release_note"}


def test_deploy_sql_targets_agents_schema():
    sql = deploy_agent.build_sql("dev")
    assert sql[0] == "create schema if not exists NOI_DEV.AGENTS"
    assert sql[1].startswith("create or replace agent NOI_DEV.AGENTS.NETWORK_OPS_AGENT")


def test_partner_agent_has_no_case_history_and_uses_public_docs():
    spec = yaml.safe_load(deploy_agent.render_spec("dev", "partner"))
    names = {t["tool_spec"]["name"] for t in spec["tools"]}
    assert "CaseHistory" not in names
    assert spec["tool_resources"]["KnowledgeBase"]["name"] == "NOI_DEV.SEARCH.PUBLIC_DOCS"
    assert "SUPPORT_DOCS" not in deploy_agent.render_spec("dev", "partner").split("tool_resources")[1]


def test_deploy_grants_usage_only_to_the_agents_audience():
    internal = "\n".join(deploy_agent.build_sql("dev", "internal"))
    partner = "\n".join(deploy_agent.build_sql("dev", "partner"))
    assert "grant usage on agent NOI_DEV.AGENTS.NETWORK_OPS_AGENT to role NOI_SUPPORT" in internal
    assert "NOI_PARTNER" not in internal
    assert "grant usage on agent NOI_DEV.AGENTS.NETWORK_OPS_PARTNER_AGENT to role NOI_PARTNER_PTR_001" in partner
    assert "NOI_SUPPORT" not in partner
