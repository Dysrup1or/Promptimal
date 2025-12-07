"""
Promptimal v2 - Streamlit Web Interface
========================================
A web UI for the Consensus Prompt Optimizer.

Run with: streamlit run app.py
"""

import os
import json
import streamlit as st
from pathlib import Path
from datetime import datetime

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Import the v2 pipeline
from consensus_prompt_optimizer.orchestrator import PromptimaV2


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Promptimal - Prompt Optimizer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-top: 0;
    }
    .cost-badge {
        background-color: #10B981;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.9rem;
    }
    .stage-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #667eea;
    }
    .prompt-output {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 20px;
        border-radius: 8px;
        font-family: 'Consolas', monospace;
        white-space: pre-wrap;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SIDEBAR - CONFIGURATION
# ============================================================================
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    
    # API Key Status
    st.markdown("### 🔑 API Keys")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    
    if gemini_key:
        st.success("✅ Gemini API Key loaded")
    else:
        st.error("❌ Gemini API Key missing")
        gemini_key = st.text_input("Enter Gemini API Key:", type="password")
        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key
    
    if deepseek_key:
        st.success("✅ DeepSeek API Key loaded")
    else:
        st.error("❌ DeepSeek API Key missing")
        deepseek_key = st.text_input("Enter DeepSeek API Key:", type="password")
        if deepseek_key:
            os.environ["DEEPSEEK_API_KEY"] = deepseek_key
    
    st.divider()
    
    # Options
    st.markdown("### 🛠️ Options")
    use_cache = st.checkbox("Use cache", value=True, help="Cache results to avoid re-running identical prompts")
    dry_run = st.checkbox("Dry run mode", value=False, help="Test without making API calls")
    show_details = st.checkbox("Show stage details", value=True, help="Display intermediate stage outputs")
    
    st.divider()
    
    # About
    st.markdown("### ℹ️ About")
    st.markdown("""
    **Promptimal v2** uses a 5-stage pipeline:
    1. 🔍 **Discerner** - Analyze intent
    2. 📋 **CriticFirst** - Generate rubric
    3. 🎨 **Expander** - Create variations
    4. 🏆 **Ranker** - Rank variations
    5. ✨ **Synthesizer** - Final prompt
    
    Cost: ~$0.0005/run (mostly free!)
    """)


# ============================================================================
# MAIN CONTENT
# ============================================================================
st.markdown('<p class="main-header">🎯 Promptimal</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Transform your ideas into bulletproof prompts</p>', unsafe_allow_html=True)

st.divider()

# Input Section
st.markdown("### 💡 Your Prompt Idea")
idea = st.text_area(
    "Enter your prompt idea:",
    placeholder="Example: Write a prompt that helps an AI assistant explain complex scientific concepts to children aged 8-12",
    height=100,
    label_visibility="collapsed"
)

# Example prompts
with st.expander("📚 Example Ideas"):
    examples = [
        "Create a prompt for generating creative blog post titles",
        "Write a prompt that helps debug Python code with clear explanations",
        "Design a prompt for summarizing long documents while preserving key insights",
        "Create a prompt for generating SQL queries from natural language",
        "Write a prompt that helps brainstorm startup ideas in a specific domain",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            idea = ex
            st.rerun()

# Run button
col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    run_button = st.button("🚀 Optimize Prompt", type="primary", use_container_width=True)

st.divider()

# ============================================================================
# PROCESSING & RESULTS
# ============================================================================
if run_button and idea:
    # Check API keys
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("DEEPSEEK_API_KEY"):
        st.error("⚠️ Please configure API keys in the sidebar first!")
    else:
        # Run the pipeline
        with st.spinner("🔄 Optimizing your prompt... (this takes 10-30 seconds)"):
            try:
                optimizer = PromptimaV2(
                    use_cache=use_cache,
                    dry_run=dry_run
                )
                result = optimizer.run(idea)
                
                # Store in session state
                st.session_state['last_result'] = result
                st.session_state['last_idea'] = idea
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.exception(e)
                result = None

# Display results if available
if 'last_result' in st.session_state:
    result = st.session_state['last_result']
    
    # Success message with cost
    cost = result.get('usage', {}).get('total_cost_usd', 0)
    st.success(f"✅ Prompt optimized successfully! Cost: ${cost:.6f}")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Final Prompt", "📊 Variations", "📋 Analysis", "📄 Raw JSON"])
    
    with tab1:
        st.markdown("### ✨ Optimized Prompt")
        final = result.get('final_synthesis', {})
        prompt_text = final.get('prompt', 'No prompt generated')
        
        # Display the prompt in a nice box
        st.markdown(f'<div class="prompt-output">{prompt_text}</div>', unsafe_allow_html=True)
        
        # Copy button
        st.code(prompt_text, language=None)
        
        # Synthesis notes
        if final.get('notes'):
            st.markdown("#### 📝 Synthesis Notes")
            st.info(final.get('notes'))
        
        # Rubric compliance
        if final.get('rubric_compliance'):
            st.markdown("#### ✅ Rubric Compliance")
            for criterion, explanation in final.get('rubric_compliance', {}).items():
                st.markdown(f"**{criterion}:** {explanation}")
    
    with tab2:
        st.markdown("### 🎨 Generated Variations")
        variations = result.get('variations', {})
        
        for var_id in ['A', 'B', 'C']:
            var = variations.get(var_id, {})
            if var:
                rank = var.get('rank', '?')
                score = var.get('score', 0)
                
                # Color based on rank
                colors = {1: '#10B981', 2: '#F59E0B', 3: '#EF4444'}
                color = colors.get(rank, '#666')
                
                st.markdown(f"""
                <div class="stage-card" style="border-left-color: {color};">
                    <strong>Variation {var_id}</strong> - Rank #{rank} (Score: {score:.2f})
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"**Prompt:**")
                st.code(var.get('prompt', 'N/A'), language=None)
                st.markdown(f"**Notes:** {var.get('notes', 'N/A')}")
                st.markdown(f"**Checklist Score:** {var.get('checklist_score', 'N/A')}")
                st.divider()
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔍 Task Analysis")
            analysis = result.get('task_analysis', {})
            st.json(analysis)
        
        with col2:
            st.markdown("### 📋 Rubric")
            rubric = result.get('rubric', {})
            
            if rubric.get('criteria'):
                st.markdown("**Criteria:**")
                for name, desc in rubric.get('criteria', {}).items():
                    st.markdown(f"- **{name}:** {desc[:100]}...")
            
            if rubric.get('checklist'):
                st.markdown("**Checklist:**")
                for item in rubric.get('checklist', [])[:5]:
                    st.markdown(f"- {item}")
            
            if rubric.get('red_flags'):
                st.markdown("**Red Flags:**")
                for flag in rubric.get('red_flags', [])[:3]:
                    st.markdown(f"- ⚠️ {flag}")
        
        # Usage statistics
        st.markdown("### 📊 Usage Statistics")
        usage = result.get('usage', {})
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Calls", usage.get('total_calls', 0))
        col2.metric("Input Tokens", usage.get('total_input_tokens', 0))
        col3.metric("Output Tokens", usage.get('total_output_tokens', 0))
        col4.metric("Total Cost", f"${usage.get('total_cost_usd', 0):.6f}")
        
        # Stage breakdown
        if usage.get('by_stage'):
            st.markdown("**Stage Breakdown:**")
            stage_data = []
            for stage in usage.get('by_stage', []):
                stage_data.append({
                    "Stage": stage.get('stage', '').title(),
                    "Model": stage.get('model', '').split('/')[-1],
                    "Input": stage.get('input_tokens', 0),
                    "Output": stage.get('output_tokens', 0),
                    "Cost": f"${stage.get('cost', 0):.6f}"
                })
            st.table(stage_data)
    
    with tab4:
        st.markdown("### 📄 Full JSON Output")
        st.json(result)
        
        # Download button
        json_str = json.dumps(result, indent=2)
        st.download_button(
            label="📥 Download JSON",
            data=json_str,
            file_name=f"promptimal_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

elif run_button and not idea:
    st.warning("⚠️ Please enter a prompt idea first!")


# ============================================================================
# FOOTER
# ============================================================================
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    Promptimal v2 | Judge-then-Generate Pipeline | 
    <a href="https://github.com/your-repo" target="_blank">GitHub</a>
</div>
""", unsafe_allow_html=True)
