from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from streamlit.components.v1 import html

API_BASE = os.getenv('MAZE_API_BASE', 'http://127.0.0.1:8000')


# ============================================================================
# Custom CSS for 2003 Terminal Vibe
# ============================================================================
def inject_terminal_css():
    """Inject custom CSS for eerie 2003 console terminal aesthetics."""
    st.markdown("""
    <style>
    /* Import monospace font */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Courier+Prime&display=swap');
    
    /* ROOT VARIABLES */
    :root {
        --terminal-bg: #000000;
        --terminal-fg: #00ff41;
        --terminal-accent: #55f5ff;
        --terminal-muted: #4a4a4a;
        --terminal-warning: #ff6b8b;
        --terminal-glitch: #ffec99;
    }
    
    /* GLOBAL OVERRIDES */
    .stApp {
        background: #000000 !important;
        color: #00ff41 !important;
        font-family: 'IBM Plex Mono', 'Courier Prime', 'Courier New', monospace !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Scanlines effect */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
            rgba(18, 16, 16, 0) 50%, 
            rgba(0, 0, 0, 0.25) 50%
        );
        background-size: 100% 4px;
        pointer-events: none;
        z-index: 999;
        animation: scanline 8s linear infinite;
    }
    
    @keyframes scanline {
        0% { background-position: 0 0; }
        100% { background-position: 0 100%; }
    }
    
    /* CRT flicker effect */
    .stApp::after {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(18, 16, 16, 0.1);
        opacity: 0;
        pointer-events: none;
        z-index: 998;
        animation: flicker 0.15s infinite;
    }
    
    @keyframes flicker {
        0% { opacity: 0.27861; }
        5% { opacity: 0.34769; }
        10% { opacity: 0.23604; }
        15% { opacity: 0.90626; }
        20% { opacity: 0.18128; }
        25% { opacity: 0.83891; }
        30% { opacity: 0.65583; }
        35% { opacity: 0.67807; }
        40% { opacity: 0.26559; }
        45% { opacity: 0.84693; }
        50% { opacity: 0.96019; }
        55% { opacity: 0.08594; }
        60% { opacity: 0.20313; }
        65% { opacity: 0.71988; }
        70% { opacity: 0.53455; }
        75% { opacity: 0.37288; }
        80% { opacity: 0.71428; }
        85% { opacity: 0.70419; }
        90% { opacity: 0.7003; }
        95% { opacity: 0.36108; }
        100% { opacity: 0.24387; }
    }
    
    /* Terminal header */
    .terminal-header {
        background: #0a0a0a;
        border: 1px solid #00ff41;
        border-radius: 3px;
        padding: 1rem;
        margin-bottom: 2rem;
        font-family: 'IBM Plex Mono', monospace;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
    }
    
    .terminal-prompt {
        color: #55f5ff;
        text-shadow: 0 0 8px rgba(85, 245, 255, 0.6);
    }
    
    .terminal-cursor {
        animation: blink 1s step-end infinite;
    }
    
    @keyframes blink {
        50% { opacity: 0; }
    }
    
    /* Story paragraphs */
    .story-paragraph {
        background: rgba(0, 20, 0, 0.4);
        border-left: 2px solid #00ff41;
        padding: 1.5rem 2rem;
        margin: 1.5rem 0;
        line-height: 1.9;
        font-size: 1.1rem;
        letter-spacing: 0.02em;
        color: #00ff41;
        text-shadow: 0 0 5px rgba(0, 255, 65, 0.4);
        transition: all 0.5s ease;
        position: relative;
        transform-origin: left center;
    }
    
    .story-paragraph::before {
        content: ">";
        position: absolute;
        left: 0.5rem;
        color: #55f5ff;
        font-weight: bold;
        transition: opacity 0.5s ease;
    }

    /* Past paragraphs */
    .story-paragraph.past {
        opacity: 0.4;
        filter: blur(2px);
        transform: translateX(-10px) scale(0.98);
        border-left-color: rgba(0, 255, 65, 0.3);
        cursor: pointer;
    }

    .story-paragraph.past::before {
        opacity: 0.3;
    }
    
    /* Hover effects */
    .story-paragraph.past:hover {
        opacity: 0.7;
        filter: blur(1px);
        transform: translateX(-5px) scale(0.99);
        border-left-color: #55f5ff;
        background: rgba(0, 40, 0, 0.6);
    }
    
    /* Active/current paragraph */
    .story-paragraph.current {
        background: rgba(0, 40, 0, 0.6);
        border-left-color: #55f5ff;
        transform: translateX(0) scale(1);
        opacity: 1;
        filter: none;
        text-shadow: 0 0 10px rgba(0, 255, 65, 0.8);
    }
    
    /* Mutation effects */
    .story-paragraph.mutating {
        animation: glitch 0.3s ease-in-out;
        color: #ffec99;
    }
    
    .story-paragraph.mutating::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(255, 236, 153, 0.1) 50%,
            transparent 100%);
        animation: sweep 1s linear;
        pointer-events: none;
    }

    @keyframes sweep {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }

    /* Short paragraph warning */
    .story-paragraph.short {
        border-left-color: #ff6b8b;
    }
    
    .story-paragraph.short::after {
        content: "[SIGNAL WEAK - BUFFERING NARRATIVE]";
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        font-size: 0.7rem;
        color: #ff6b8b;
        letter-spacing: 0.1em;
    }
    
    @keyframes glitch {
        0% { transform: translateX(0); }
        20% { transform: translateX(-1px); }
        40% { transform: translateX(1px); }
        60% { transform: translateX(-0.5px); }
        80% { transform: translateX(0.5px); }
        100% { transform: translateX(0); }
    }
    
    /* Paragraph index */
    .paragraph-index {
        color: #4a4a4a;
        font-size: 0.75rem;
        margin-right: 1rem;
        font-weight: bold;
    }
    
    /* Branch/Decision styling */
    .branch-container {
        border: 2px dashed #55f5ff;
        padding: 2rem;
        margin: 2rem 0;
        background: rgba(0, 30, 30, 0.3);
        position: relative;
    }
    
    .branch-container::before {
        content: "FORK IN THE MAZE";
        position: absolute;
        top: -0.7rem;
        left: 1rem;
        background: #000000;
        padding: 0 0.5rem;
        color: #55f5ff;
        font-size: 0.7rem;
        letter-spacing: 0.3em;
    }
    
    .branch-instruction {
        color: #ffec99;
        text-align: center;
        margin-bottom: 1.5rem;
        font-size: 0.85rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
    }
    
    /* Buttons - terminal style */
    .stButton > button {
        background: transparent !important;
        color: #00ff41 !important;
        border: 2px solid #00ff41 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        letter-spacing: 0.15em !important;
        text-transform: uppercase !important;
        padding: 0.75rem 2rem !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.3) !important;
    }
    
    .stButton > button:hover {
        background: #00ff41 !important;
        color: #000000 !important;
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.6) !important;
        transform: translateY(-2px);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Sidebar - hide it for immersive experience */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Status messages */
    .status-bar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #0a0a0a;
        border-bottom: 1px solid #00ff41;
        padding: 0.5rem 1rem;
        z-index: 1000;
        font-size: 0.75rem;
        letter-spacing: 0.2em;
        color: #4a4a4a;
    }
    
    .status-connected {
        color: #00ff41;
    }
    
    /* Scroll indicator */
    .scroll-indicator {
        position: fixed;
        bottom: 2rem;
        left: 50%;
        transform: translateX(-50%);
        color: #55f5ff;
        font-size: 0.8rem;
        letter-spacing: 0.3em;
        animation: pulse 2s ease-in-out infinite;
        text-shadow: 0 0 10px rgba(85, 245, 255, 0.6);
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
    }
    
    /* Loading animations */
    @keyframes loadbar {
        0% { width: 0; opacity: 0.8; }
        90% { width: 90%; opacity: 0.8; }
        100% { width: 100%; opacity: 0; }
    }

    @keyframes blink-cursor {
        0%, 100% { opacity: 0; }
        50% { opacity: 1; }
    }

    .loading-container {
        font-family: "IBM Plex Mono", monospace;
        padding: 2rem;
        background: rgba(0, 10, 0, 0.3);
        border: 1px solid #00ff41;
        margin: 2rem 0;
        position: relative;
    }

    .loading-container::before {
        content: "[PROCESSING NARRATIVE STREAM]";
        position: absolute;
        top: -0.7rem;
        left: 1rem;
        background: #000000;
        padding: 0 0.5rem;
        font-size: 0.7rem;
        letter-spacing: 0.2em;
        color: #00ff41;
    }

    .loading-text {
        color: #00ff41;
        font-size: 0.9rem;
        letter-spacing: 0.15em;
        margin-bottom: 1rem;
        font-family: inherit;
    }

    .loading-bar {
        height: 1px;
        background: #00ff41;
        width: 0;
        animation: loadbar 3s ease-in-out infinite;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.4);
    }

    .loading-cursor {
        display: inline-block;
        width: 0.6em;
        height: 1em;
        background: #00ff41;
        margin-left: 0.2em;
        animation: blink-cursor 0.8s step-end infinite;
        vertical-align: middle;
    }

    .loading-status {
        color: #4a4a4a;
        font-size: 0.75rem;
        letter-spacing: 0.1em;
        margin-top: 0.5rem;
        font-family: inherit;
    }
    
    /* Text input - terminal style */
    .stTextInput > div > div > input {
        background: #0a0a0a !important;
        color: #00ff41 !important;
        border: 1px solid #00ff41 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        letter-spacing: 0.1em !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #55f5ff !important;
        box-shadow: 0 0 10px rgba(85, 245, 255, 0.4) !important;
    }
    
    /* Markdown overrides */
    .stMarkdown {
        color: #00ff41 !important;
    }
    
    /* Main content padding for status bar */
    .main .block-container {
        padding-top: 4rem !important;
        max-width: 900px !important;
    }
    
    /* Registration form */
    .registration-overlay {
        background: rgba(0, 0, 0, 0.95);
        border: 2px solid #ff6b8b;
        padding: 2rem;
        margin: 2rem 0;
        box-shadow: 0 0 30px rgba(255, 107, 139, 0.4);
    }
    
    .registration-title {
        color: #ff6b8b;
        text-align: center;
        letter-spacing: 0.3em;
        font-size: 1rem;
        margin-bottom: 1.5rem;
        text-transform: uppercase;
    }
    
    /* Hide default streamlit elements for cleaner look */
    .stDeployButton {display: none;}
    .stDecoration {display: none;}
    </style>
    """, unsafe_allow_html=True)


# ============================================================================
# API Communication
# ============================================================================
def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = requests.post(f'{API_BASE}{path}', json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f'⚠ CONNECTION LOST: {exc}')
        return {}


def api_get(path: str) -> Dict[str, Any]:
    try:
        response = requests.get(f'{API_BASE}{path}', timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f'⚠ CONNECTION LOST: {exc}')
        return {}


# ============================================================================
# Session Management
# ============================================================================
def init_session() -> Optional[Dict[str, Any]]:
    """Initialize or retrieve existing session."""
    if 'maze_session' not in st.session_state:
        profile_name = st.session_state.get('profile_name')
        payload = api_post('/api/session', {'profile_name': profile_name})
        if payload:
            st.session_state.maze_session = payload
            st.session_state.story_feed = []  # Initialize story feed
            st.session_state.auto_scroll = True
            st.session_state.scroll_position = 0
    return st.session_state.get('maze_session')


def advance_story() -> Optional[Dict[str, Any]]:
    """Advance the story automatically on scroll."""
    session = st.session_state.get('maze_session')
    if not session:
        return None
    
    # Don't advance if there's a pending decision
    if session.get('pending_decision'):
        return session
    
    try:
        data = api_post(
            '/api/progress',
            {
                'session_id': session['session_id'],
                'event': 'advance',
            },
        )
        if data:
            session.update(data)
            st.session_state.maze_session = session
            
            # Add new paragraphs to the feed
            if 'paragraphs' in data:
                for para in data['paragraphs']:
                    st.session_state.story_feed.append({
                        'type': 'paragraph',
                        'content': para,
                        'timestamp': time.time()
                    })
            
            # Add branch if present
            if data.get('branch'):
                st.session_state.story_feed.append({
                    'type': 'branch',
                    'content': data['branch'],
                    'timestamp': time.time()
                })
        
        return session
    except Exception as exc:
        st.error(f'⚠ MAZE ERROR: {exc}')
        return session


def make_decision(direction: str) -> Optional[Dict[str, Any]]:
    """Make a decision at a branch point."""
    session = st.session_state.get('maze_session')
    if not session:
        return None
    
    try:
        data = api_post(
            '/api/progress',
            {
                'session_id': session['session_id'],
                'event': 'decision',
                'direction': direction,
                'via': 'streamlit_v2',
            },
        )
        if data:
            session.update(data)
            st.session_state.maze_session = session
            
            # Add decision result to feed
            if 'paragraphs' in data:
                for para in data['paragraphs']:
                    st.session_state.story_feed.append({
                        'type': 'paragraph',
                        'content': para,
                        'timestamp': time.time()
                    })
        
        return session
    except Exception as exc:
        st.error(f'⚠ DECISION FAILED: {exc}')
        return session


# ============================================================================
# Rendering Components
# ============================================================================
def render_terminal_header(session: Dict[str, Any]):
    """Render the terminal-style header."""
    scene_id = session.get('scene_id', 'UNKNOWN')
    emotional_track = session.get('emotional_track', 'NEUTRAL')
    
    st.markdown(f"""
    <div class="terminal-header">
        <span class="terminal-prompt">root@DEADLIGHT_2003:~$</span> 
        <span style="color: #00ff41;">STATUS: CONNECTED</span><br/>
        <span style="color: #4a4a4a; font-size: 0.75rem;">
            SCENE: {scene_id} | TRACK: {emotional_track.upper()} | SESSION: {session.get('session_id', '')[:8]}...
        </span>
        <span class="terminal-cursor">█</span>
    </div>
    """, unsafe_allow_html=True)


def render_paragraph(para: Dict[str, Any], index: int):
    """Render a single story paragraph with terminal styling."""
    text = para.get('text', '')
    glitch_class = 'glitch' if para.get('mutations') else ''
    
    st.markdown(f"""
    <div class="story-paragraph {glitch_class}">
        <span class="paragraph-index">[{index:03d}]</span>
        {text}
    </div>
    """, unsafe_allow_html=True)


def render_branch(branch: Dict[str, Any]):
    """Render a decision branch point."""
    st.markdown(f"""
    <div class="branch-container">
        <div class="branch-instruction">
            {branch.get('instruction', 'THE MAZE AWAITS YOUR CHOICE')}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    options = branch.get('options', [])
    cols = st.columns(len(options))
    
    for col, option in zip(cols, options):
        with col:
            label = option.get('label', 'UNKNOWN')
            direction = option.get('direction', 'left')
            body = option.get('body', '')
            
            st.markdown(f"""
            <div style="text-align: center; margin-bottom: 1rem;">
                <div style="color: #55f5ff; font-size: 0.7rem; letter-spacing: 0.2em; margin-bottom: 0.5rem;">
                    {label}
                </div>
                <div style="color: #4a4a4a; font-size: 0.85rem; line-height: 1.6;">
                    {body}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"CHOOSE: {label}", key=f"branch_{direction}"):
                make_decision(direction)
                st.rerun()


def render_story_feed():
    """Render the entire story feed as an infinite scroll."""
    feed = st.session_state.get('story_feed', [])
    
    if not feed:
        st.markdown("""
        <div class="loading">
            INITIALIZING MAZE...
        </div>
        """, unsafe_allow_html=True)
        return
    
    para_count = 1
    for item in feed:
        if item['type'] == 'paragraph':
            render_paragraph(item['content'], para_count)
            para_count += 1
        elif item['type'] == 'branch':
            render_branch(item['content'])


def render_scroll_prompt(session: Dict[str, Any]):
    """Show scroll indicator if more content is available."""
    if not session.get('pending_decision') and not session.get('story_complete'):
        st.markdown("""
        <div class="scroll-indicator">
            ↓ SCROLL TO DESCEND DEEPER ↓
        </div>
        """, unsafe_allow_html=True)


def render_registration_form(session: Dict[str, Any]):
    """Render the registration form when unlocked."""
    if not session.get('allow_registration'):
        return
    
    st.markdown("""
    <div class="registration-overlay">
        <div class="registration-title">
            ◈ CHAPTER ONE COMPLETE ◈<br/>
            REGISTER TO CONTINUE THE MAZE
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("registration_form"):
        name = st.text_input("NAME", placeholder="Enter your name...")
        email = st.text_input("EMAIL", placeholder="Enter your email...")
        
        if st.form_submit_button("⟩ SUBMIT & AWAIT CHAPTER TWO"):
            if name and email:
                result = api_post(
                    '/api/register',
                    {
                        'name': name,
                        'email': email,
                        'session_id': session['session_id'],
                    },
                )
                if result:
                    st.success("✓ REGISTERED. THE MAZE WILL FIND YOU WHEN CHAPTER TWO STABILIZES.")


# ============================================================================
# Auto-scroll mechanism using JavaScript
# ============================================================================
def inject_auto_scroll_detector():
    """Inject JavaScript to detect when user scrolls near bottom."""
    scroll_js = """
    <script>
    let lastScrollTop = 0;
    let ticking = false;
    
    function checkScroll() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight;
        const clientHeight = document.documentElement.clientHeight;
        const scrolledToBottom = (scrollTop + clientHeight) >= (scrollHeight - 200);
        
        if (scrolledToBottom && scrollTop > lastScrollTop) {
            // User scrolled to bottom - trigger rerun
            const event = new CustomEvent('streamlit:setComponentValue', {
                detail: {value: Date.now()}
            });
            window.dispatchEvent(event);
        }
        
        lastScrollTop = scrollTop;
        ticking = false;
    }
    
    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(checkScroll);
            ticking = true;
        }
    });
    </script>
    """
    html(scroll_js, height=0)


# ============================================================================
# Main Application
# ============================================================================
def main():
    st.set_page_config(
        page_title="DEADLIGHT 2003 ◈ THE MAZE",
        page_icon="🌲",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Inject custom CSS
    inject_terminal_css()
    
    # Initialize session
    session = init_session()
    if not session:
        st.error("⚠ FAILED TO INITIALIZE MAZE SESSION")
        st.stop()
    
    # Render terminal header
    render_terminal_header(session)
    
    # Initialize story feed if empty
    if not st.session_state.get('story_feed'):
        if session.get('paragraphs'):
            for para in session['paragraphs']:
                st.session_state.story_feed.append({
                    'type': 'paragraph',
                    'content': para,
                    'timestamp': time.time()
                })
        if session.get('branch'):
            st.session_state.story_feed.append({
                'type': 'branch',
                'content': session['branch'],
                'timestamp': time.time()
            })
    
    # Render the story feed
    render_story_feed()
    
    # Show scroll prompt
    render_scroll_prompt(session)
    
    # Registration form
    render_registration_form(session)
    
    # Manual advance button (hidden at bottom for development)
    if st.button("⟩ ADVANCE MANUALLY", key="manual_advance", help="Dev control"):
        advance_story()
        st.rerun()
    
    # Auto-scroll detector (triggers advance on scroll)
    # inject_auto_scroll_detector()
    
    # Auto-advance after a delay if no pending decision
    if not session.get('pending_decision') and not session.get('story_complete'):
        time.sleep(0.1)  # Small delay to allow rendering
        if st.button("↓ Continue deeper into the maze", key="continue_btn", use_container_width=True):
            advance_story()
            st.rerun()


if __name__ == '__main__':
    main()
