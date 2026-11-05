"""
backend/app/api/routes/rea.py
─────────────────────────────
REA reverse-engineering endpoints for UI analysis and recommendations.

Endpoints
─────────
  GET /api/v1/rea/recommendations       UI enhancement recommendations
  GET /api/v1/rea/patterns/{component}  Extract patterns from component
  GET /api/v1/rea/competitor/{system}   Analyze competitor UI patterns
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.app.auth import require_user
from backend.app.services.rea_integration import get_rea_service

router = APIRouter(dependencies=[Depends(require_user)])
logger = logging.getLogger(__name__)


@router.get("/rea/recommendations")
def get_ui_recommendations():
    """
    Generate UI enhancement recommendations based on:
    - Current KAIROS component analysis
    - Competitor system patterns (DataHub, OpenMetadata, Atlan)
    - User feedback and usage patterns
    
    Returns recommendations organized by component area with:
    - Priority level
    - Complexity estimate
    - Reference implementation from competitor
    - Expected user benefit
    """
    rea = get_rea_service()
    result = rea.generate_ui_recommendations()
    
    logger.info(f"[REA] Generated UI recommendations: {len(result.get('recommendations', {}))} sections")
    
    return {
        "operation": "get_ui_recommendations",
        **result,
    }


@router.get("/rea/patterns/search")
def analyze_search_component():
    """Extract patterns from SearchPage component."""
    rea = get_rea_service()
    
    patterns = rea.extract_component_patterns(
        "frontend/src/components/SearchPage"
    )
    
    logger.info(f"[REA] Analyzed SearchPage patterns")
    
    return {
        "component": "SearchPage",
        "patterns": patterns,
    }


@router.get("/rea/patterns/entity")
def analyze_entity_component():
    """Extract patterns from EntityPage component."""
    rea = get_rea_service()
    
    patterns = rea.extract_component_patterns(
        "frontend/src/components/EntityPage"
    )
    
    logger.info(f"[REA] Analyzed EntityPage patterns")
    
    return {
        "component": "EntityPage",
        "patterns": patterns,
    }


@router.get("/rea/patterns/evidence")
def analyze_evidence_component():
    """Extract patterns from EvidenceInspector component."""
    rea = get_rea_service()
    
    patterns = rea.extract_component_patterns(
        "frontend/src/components/Inspector/EvidenceInspector"
    )
    
    logger.info(f"[REA] Analyzed EvidenceInspector patterns")
    
    return {
        "component": "EvidenceInspector",
        "patterns": patterns,
    }


@router.get("/rea/competitor/{system}")
def analyze_competitor_system(
    system: str,
):
    """
    Analyze UI patterns from competitor metadata systems.
    
    Parameters:
        system: Competitor system name (datahub, openmetadata, or atlan)
    
    Returns:
        Key UI patterns and design decisions from the competitor system
    """
    valid_systems = ["datahub", "openmetadata", "atlan"]
    if system.lower() not in valid_systems:
        return {
            "error": f"Invalid system: {system}. Must be one of: {', '.join(valid_systems)}",
            "valid_systems": valid_systems,
        }
    
    rea = get_rea_service()
    result = rea.analyze_competitor_patterns(system.lower())
    
    logger.info(f"[REA] Analyzed {system} competitor patterns")
    
    return result


@router.get("/rea/analysis/components")
def analyze_all_components():
    """
    Analyze all KAIROS frontend components and extract patterns.
    
    Covers:
    - SearchPage (discovery interface)
    - EntityPage (details view)
    - EvidenceInspector (reasoning panel)
    - LineageGraph (interactive visualization)
    - Plus supporting components
    """
    rea = get_rea_service()
    
    components = {
        "search_page": rea.extract_component_patterns("frontend/src/components/SearchPage"),
        "entity_page": rea.extract_component_patterns("frontend/src/components/EntityPage"),
        "evidence_inspector": rea.extract_component_patterns("frontend/src/components/Inspector/EvidenceInspector"),
    }
    
    logger.info(f"[REA] Analyzed all components")
    
    return {
        "operation": "analyze_all_components",
        "components": components,
    }


@router.get("/rea/implementation-guide")
def get_implementation_guide(
    component: Optional[str] = Query(None, description="Specific component to guide (search, entity, evidence, lineage)")
):
    """
    Generate implementation guide based on REA analysis of competitor systems.
    
    Shows step-by-step how to implement recommended features by:
    1. Identifying similar component in competitor system
    2. Extracting key implementation patterns
    3. Adapting to KAIROS architecture
    """
    guide = {
        "operation": "get_implementation_guide",
        "summary": "Step-by-step guide to implement UI recommendations based on competitor analysis",
        "steps": [
            {
                "phase": "1. Pattern Analysis",
                "description": "Use REA to extract UI patterns from competitor (DataHub/OpenMetadata/Atlan)",
                "example": "rea analyze-javascript-application /path/to/datahub/web-src",
                "output": "Module structure, imports, component hierarchy",
            },
            {
                "phase": "2. Design Adaptation",
                "description": "Map competitor pattern to KAIROS architecture",
                "considerations": [
                    "React version compatibility",
                    "State management (React Query, Redux, etc.)",
                    "API contract alignment",
                    "Styling system (Tailwind, Material-UI, etc.)",
                    "Accessibility requirements",
                ],
            },
            {
                "phase": "3. Implementation",
                "description": "Build the feature in KAIROS",
                "checklist": [
                    "Create component or modify existing",
                    "Wire to backend API",
                    "Add state management",
                    "Implement error handling",
                    "Add loading states",
                ],
            },
            {
                "phase": "4. Verification",
                "description": "Test against original pattern",
                "validation": [
                    "Visual regression testing",
                    "Interaction testing",
                    "Performance profiling",
                    "Accessibility audit (WCAG 2.1)",
                ],
            },
        ],
        "recommended_next_features": [
            {
                "feature": "Column-level lineage",
                "reference": "OpenMetadata",
                "effort": "high",
                "impact": "critical",
            },
            {
                "feature": "Data quality badges",
                "reference": "Atlan",
                "effort": "medium",
                "impact": "high",
            },
            {
                "feature": "Saved searches",
                "reference": "DataHub",
                "effort": "medium",
                "impact": "high",
            },
            {
                "feature": "Owner assignment",
                "reference": "Atlan",
                "effort": "medium",
                "impact": "medium",
            },
        ],
    }
    
    if component:
        # Filter to specific component
        if component.lower() == "search":
            guide["focused_component"] = "SearchPage"
            guide["recommendations"] = [
                "Add saved search filters (DataHub pattern)",
                "Implement full-text search",
                "Show search history",
            ]
        elif component.lower() == "entity":
            guide["focused_component"] = "EntityPage"
            guide["recommendations"] = [
                "Add owner/steward assignment (Atlan)",
                "Implement inline tagging",
                "Add data quality scorecard (OpenMetadata)",
            ]
        elif component.lower() == "evidence":
            guide["focused_component"] = "EvidenceInspector"
            guide["recommendations"] = [
                "Add evidence timeline",
                "Show confidence scores",
                "Implement evidence comparison",
            ]
        elif component.lower() == "lineage":
            guide["focused_component"] = "LineageGraph"
            guide["recommendations"] = [
                "Add column-level lineage toggle",
                "Implement path highlighting",
                "Add impact analysis",
            ]
    
    return guide
