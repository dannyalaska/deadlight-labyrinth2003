/* ================================================================== */
/*  DEADLIGHT 2003 — dreams_and_static                               */
/*  Forum frontend — page-type renderers                              */
/* ================================================================== */

const API_BASE = '';

/* ------------------------------------------------------------------ */
/*  DOM references                                                     */
/* ------------------------------------------------------------------ */
const el = {
  forumTitle: document.getElementById('forumTitle'),
  forumTagline: document.getElementById('forumTagline'),
  headerStatus: document.getElementById('headerStatus'),
  breadcrumb: document.getElementById('breadcrumb'),
  content: document.getElementById('forumContent'),
  navHome: document.getElementById('navHome'),
  navTos: document.getElementById('navTos'),
  snackbar: document.getElementById('snackbar'),
  bannerAd: document.getElementById('bannerAd'),
  bannerAdText: document.getElementById('bannerAdText'),
  bannerAdX: document.getElementById('bannerAdX'),
};

/* ------------------------------------------------------------------ */
/*  State                                                              */
/* ------------------------------------------------------------------ */
let currentSession = null;
let pendingRequest = null;
let activeTimers = [];          // all pending setTimeout IDs — cleared on navigation
let lastForumIndex = 'forum_index';  // tracks which forum index to breadcrumb to
let corruptionLevel = 0;        // 0-4: visual corruption level from ad clicks

/* ------------------------------------------------------------------ */
/*  Bootstrap                                                          */
/* ------------------------------------------------------------------ */
document.addEventListener('DOMContentLoaded', init);

async function init() {
  bindUIEvents();
  try {
    await startSession();
  } catch (error) {
    console.error('Failed to bootstrap', error);
    el.headerStatus.textContent = 'offline';
    showSnackbar('Connection failed.');
  }
}

function bindUIEvents() {
  el.navHome?.addEventListener('click', (e) => {
    e.preventDefault();
    if (currentSession) navigateToScene(lastForumIndex);
  });
  el.navTos?.addEventListener('click', (e) => {
    e.preventDefault();
    if (currentSession) navigateToScene('tos_page');
  });

  // Banner ad — corruption mechanic
  el.bannerAd?.addEventListener('click', (e) => {
    if (e.target === el.bannerAdX) {
      // "Close" the ad — it just comes back differently
      corruptionLevel = Math.min(corruptionLevel + 1, 4);
      applyCorruption();
      updateBannerAd();
      // Briefly hide and reshow
      el.bannerAd.style.display = 'none';
      setTimeout(() => {
        const currentAct = document.body.getAttribute('data-act');
        if (el.bannerAd && (currentAct === '2' || currentAct === '3')) {
          el.bannerAd.style.display = '';
        }
      }, 3000);
    } else {
      corruptionLevel = Math.min(corruptionLevel + 1, 4);
      applyCorruption();
      updateBannerAd();
    }
  });
}

/* ------------------------------------------------------------------ */
/*  Banner ad texts — get worse with corruption level                  */
/* ------------------------------------------------------------------ */
const BANNER_AD_TEXTS = [
  'FREE AIM emoticons — click here!',
  'You have (1) unread message. Click to view.',
  'Someone is looking for you. Click to find out who.',
  '{{player_name}} — your session has not ended.',
  'you\'re still here. we kept your thread.',
];

function updateBannerAd() {
  if (!el.bannerAdText) return;
  const playerName = currentSession?.profile_name || 'you';
  const text = (BANNER_AD_TEXTS[corruptionLevel] || BANNER_AD_TEXTS[0])
    .replace('{{player_name}}', playerName);
  el.bannerAdText.textContent = text;
  el.bannerAd.setAttribute('data-level', corruptionLevel);
}

function applyCorruption() {
  document.body.setAttribute('data-corrupt', corruptionLevel);
  // Store as intake so server knows how far player went
  if (currentSession && corruptionLevel > 0) {
    apiPost('/api/intake', {
      session_id: currentSession.session_id,
      fields: { corruption_level: String(corruptionLevel) },
    }).catch(() => {});
  }
}

/* ------------------------------------------------------------------ */
/*  Session                                                            */
/* ------------------------------------------------------------------ */
async function startSession() {
  el.headerStatus.textContent = 'connecting...';
  const session = await apiPost('/api/session', {});
  handleSessionUpdate(session);
  el.headerStatus.textContent = '';
}

/* ------------------------------------------------------------------ */
/*  Navigation                                                         */
/* ------------------------------------------------------------------ */
async function navigateToScene(targetSceneId) {
  if (!currentSession) return;
  clearActiveTimers();
  showLoading();
  try {
    const session = await progressAPI('link', targetSceneId);
    handleSessionUpdate(session);
  } catch (error) {
    console.error('Navigation failed', error);
    showSnackbar('Navigation failed.');
  }
}

async function progressAPI(event, direction) {
  if (pendingRequest) return pendingRequest;
  const payload = { session_id: currentSession.session_id, event };
  if (direction) payload.direction = direction;

  pendingRequest = apiPost('/api/progress', payload).finally(() => {
    pendingRequest = null;
  });
  return pendingRequest;
}

/* ------------------------------------------------------------------ */
/*  Timer management — clears all pending timers on navigation         */
/* ------------------------------------------------------------------ */
function addTimer(id) {
  activeTimers.push(id);
}

function clearActiveTimers() {
  activeTimers.forEach(clearTimeout);
  activeTimers = [];
}

/* ------------------------------------------------------------------ */
/*  Session update — dispatch by page_type                             */
/* ------------------------------------------------------------------ */

// Act 2 — the forum knows you. warmth curdles into architecture.
const ACT2_SCENES = new Set([
  'forum_index_act2', 'deeper_thread', 'board_changes_thread',
  'old_posts_thread', 'architecture_thread',
  'signal_thread', 'ghostradio_thread', 'memory_thread', 'catalog_thread',
  'admin_panel', 'aim_return', 'source_code', 'founder_agreement',
]);

// Act 3 — the threshold. the unfinished post. the ending.
const ACT3_SCENES = new Set([
  'final_thread', 'offer_thread', 'deletion_thread',
  'accept_ending', 'refuse_ending', 'silence_ending',
  'fragment_ending', 'architect_ending',
]);

let _act2EntryDone = false;
let _act3EntryDone = false;

function handleSessionUpdate(session) {
  currentSession = session;
  clearActiveTimers();
  window.scrollTo(0, 0);

  const scene = session.scene;
  const pageType = scene.page_type || 'prose';
  const prevAct = document.body.getAttribute('data-act') || '1';

  // Determine act
  let act = '1';
  if (ACT3_SCENES.has(scene.id)) {
    act = '3';
  } else if (ACT2_SCENES.has(scene.id) || lastForumIndex === 'forum_index_act2') {
    act = '2';
  }
  const actChanged = prevAct !== act;
  document.body.setAttribute('data-act', act);

  // Banner ad visible in Act 2 and Act 3
  if (el.bannerAd) {
    const showBanner = act === '2' || act === '3';
    el.bannerAd.style.display = showBanner ? '' : 'none';
    if (showBanner) updateBannerAd();
  }

  // Update morph engine
  morphEngine.setAct(act);
  morphEngine.setScene(scene.id);

  // Act entry sweep effects — first crossing of each threshold
  if (actChanged && act === '2' && !_act2EntryDone) {
    _act2EntryDone = true;
    scheduleActEntryGlitch(false);
  }
  if (actChanged && act === '3' && !_act3EntryDone) {
    _act3EntryDone = true;
    scheduleActEntryGlitch(true);
  }

  switch (pageType) {
    case 'forum_index':   renderForumIndex(scene);  break;
    case 'forum_thread':  renderForumThread(scene); break;
    case 'profile_page':  renderProfilePage(scene); break;
    default:              renderFallback(scene);     break;
  }
}

/* ------------------------------------------------------------------ */
/*  Breadcrumb                                                         */
/* ------------------------------------------------------------------ */
function updateBreadcrumb(parts) {
  el.breadcrumb.innerHTML = '';
  parts.forEach((part, i) => {
    if (i > 0) {
      const sep = document.createElement('span');
      sep.className = 'sep';
      sep.textContent = '\u00BB';
      el.breadcrumb.appendChild(sep);
    }
    if (part.sceneId) {
      const link = document.createElement('a');
      link.href = '#';
      link.textContent = part.label;
      link.addEventListener('click', (e) => {
        e.preventDefault();
        navigateToScene(part.sceneId);
      });
      el.breadcrumb.appendChild(link);
    } else {
      const span = document.createElement('span');
      span.textContent = part.label;
      el.breadcrumb.appendChild(span);
    }
  });
}

/* ================================================================== */
/*  RENDERER: Forum Index                                              */
/* ================================================================== */
function renderForumIndex(scene) {
  const data = scene.forum_data;
  if (!data) { el.content.innerHTML = '<div class="loading-bar">No forum data.</div>'; return; }

  // Track which forum index we're on (for breadcrumbs & nav home)
  lastForumIndex = scene.id;

  updateBreadcrumb([{ label: data.board_name || 'dreams_and_static' }]);

  let html = '<table class="thread-table">';
  html += '<tr><th>Topic</th><th class="col-replies">Replies</th><th class="col-views">Views</th><th class="col-lastpost">Last Post</th></tr>';

  (data.threads || []).forEach((thread) => {
    const isToday = thread.last_post_date === 'TODAY';
    html += `<tr class="${isToday ? 'thread-row-today' : ''}">`;
    html += '<td><div class="thread-title-cell">';

    if (thread.clickable && thread.target_scene) {
      html += `<a class="thread-title-link" href="#" data-scene="${esc(thread.target_scene)}">${esc(thread.title)}</a>`;
    } else {
      html += `<span class="thread-title-text">${esc(thread.title)}</span>`;
    }
    html += `<span class="thread-author">by ${esc(thread.author)}</span>`;
    html += `<span class="thread-started">${esc(thread.started)}</span>`;
    html += '</div></td>';

    html += `<td class="col-replies">${thread.replies}</td>`;
    html += `<td class="col-views">${thread.views}</td>`;
    html += '<td class="col-lastpost">';
    html += isToday
      ? `<span class="today-badge">TODAY</span><br>`
      : `${esc(thread.last_post_date)}<br>`;
    html += `by ${esc(thread.last_post_by)}</td>`;
    html += '</tr>';
  });
  html += '</table>';

  if (data.stats) {
    html += `<div class="forum-stats">`;
    html += `<span>Total posts: <b>${data.stats.total_posts}</b></span>`;
    html += `<span>Members: <b>${data.stats.total_members}</b></span>`;
    html += `<span>Newest: <b>${esc(data.stats.newest_member)}</b></span>`;
    html += `</div>`;
  }

  el.content.innerHTML = html;

  el.content.querySelectorAll('.thread-title-link').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const sceneId = link.dataset.scene;
      if (sceneId) navigateToScene(sceneId);
    });
  });
}

/* ================================================================== */
/*  RENDERER: Forum Thread                                             */
/* ================================================================== */
function renderForumThread(scene) {
  const td = scene.thread_data;
  if (!td) { el.content.innerHTML = '<div class="loading-bar">No thread data.</div>'; return; }

  updateBreadcrumb([
    { label: td.board_name || 'dreams_and_static', sceneId: lastForumIndex },
    { label: td.thread_title || scene.title },
  ]);

  const hasLiveReply   = td.live_reply?.enabled;
  const hasDelayedHook = !!td.delayed_hook_post;

  let html = `<div class="thread-header">${esc(td.thread_title || scene.title)}</div>`;

  // Display range (e.g. "Displaying posts 1-8 of 48")
  if (td.display_range) {
    const dr = td.display_range;
    html += `<div class="thread-pagination">Displaying posts ${dr.start}-${dr.end} of ${dr.total}</div>`;
  }

  // Posts (static + generated, NOT the delayed hook post)
  const posts = td.posts || [];
  posts.forEach((post, i) => {
    html += buildPostHTML(post, i);
  });

  // Quick reply form (phpBB-style, bottom of thread — disguised intake)
  if (td.quick_reply?.enabled) {
    html += buildQuickReplyHTML(td.quick_reply);
  }

  el.content.innerHTML = html;

  // Bind links in existing posts
  bindUsernameLinks(el.content);
  bindBodyLinks(el.content);

  // Bind quick reply form
  if (td.quick_reply?.enabled) bindQuickReply(td.quick_reply);

  // Kick off async additions
  if (hasDelayedHook) setupDelayedHookPost(td.delayed_hook_post);
  if (hasLiveReply)   setupLiveReply(td.live_reply, td, scene);
}

/* ------------------------------------------------------------------ */
/*  Build a single post's HTML                                         */
/* ------------------------------------------------------------------ */
function buildPostHTML(post, index, extraClass = '') {
  const isStillHere = post.author === 'still_here_03';
  const cls = ['post-container', extraClass, isStillHere ? 'still-here-post' : ''].filter(Boolean).join(' ');
  let html = `<div class="${cls}" data-post-index="${index}">`;
  html += `<div class="post-header"><span>${esc(post.date || '')}</span><span>#${index + 1}</span></div>`;
  html += '<div class="post-body-wrap">';
  html += '<div class="post-author-panel">';

  if (post.clickable_username && post.target_scene) {
    html += `<a class="post-author-name clickable" href="#" data-scene="${esc(post.target_scene)}">${esc(post.author)}</a>`;
  } else {
    html += `<span class="post-author-name">${esc(post.author)}</span>`;
  }

  if (post.author_data) {
    html += `<div class="post-author-info">Joined: ${esc(post.author_data.joined || '')}<br>Posts: ${post.author_data.posts || 0}</div>`;
  }
  html += '</div>'; // author-panel

  // Body with optional body_links
  let bodyHtml = esc(post.body || '');
  if (post.body_links?.length) {
    post.body_links.forEach((link) => {
      const escapedLinkText = esc(link.text);
      if (bodyHtml.includes(escapedLinkText)) {
        const anchor = `<a class="post-body-link" href="#" data-scene="${esc(link.target_scene)}">${escapedLinkText}</a>`;
        bodyHtml = bodyHtml.replace(escapedLinkText, anchor);
      }
    });
  }

  html += `<div class="post-content">${bodyHtml}`;
  if (post.signature) html += `<div class="post-signature">${esc(post.signature)}</div>`;
  html += '</div>'; // post-content

  html += '</div></div>'; // post-body-wrap, post-container
  return html;
}

/* ------------------------------------------------------------------ */
/*  Bind username → scene navigation links                             */
/* ------------------------------------------------------------------ */
function bindUsernameLinks(root) {
  root.querySelectorAll('.post-author-name.clickable').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const sceneId = link.dataset.scene;
      if (sceneId) navigateToScene(sceneId);
    });
  });
}

/* ------------------------------------------------------------------ */
/*  Bind body_links → scene navigation                                 */
/* ------------------------------------------------------------------ */
function bindBodyLinks(root) {
  root.querySelectorAll('.post-body-link').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const sceneId = link.dataset.scene;
      if (sceneId) navigateToScene(sceneId);
    });
  });
}

/* ------------------------------------------------------------------ */
/*  Delayed hook post (e.g. still_here_03 "still can't do it")        */
/*  Appears after delay_ms as if it was just posted                    */
/* ------------------------------------------------------------------ */
function setupDelayedHookPost(hookPost) {
  const delay = hookPost.delay_ms || 4000;
  const timerId = setTimeout(() => {
    const postIndex = el.content.querySelectorAll('.post-container').length;
    const div = document.createElement('div');
    div.innerHTML = buildPostHTML(hookPost, postIndex, 'hook-post delayed-post');
    const postEl = div.firstChild;
    // Insert before quick reply form if present, otherwise append
    const quickReply = el.content.querySelector('.quick-reply-box');
    if (quickReply) {
      el.content.insertBefore(postEl, quickReply);
    } else {
      el.content.appendChild(postEl);
    }
    bindUsernameLinks(postEl);
    bindBodyLinks(postEl);
    postEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, delay);
  addTimer(timerId);
}

/* ------------------------------------------------------------------ */
/*  Quick Reply — phpBB-style reply box at bottom of thread            */
/*  Collects intake data disguised as forum participation              */
/* ------------------------------------------------------------------ */
function buildQuickReplyHTML(config) {
  const playerName = currentSession?.profile_name || 'you';
  let html = `<div class="quick-reply-box">`;
  html += `<div class="quick-reply-title">${esc(config.label || 'Quick Reply')}</div>`;
  html += `<form id="quickReplyForm">`;
  html += `<textarea class="reply-textarea" id="quickReplyText" placeholder="${esc(config.placeholder || 'type here...')}" rows="3"></textarea>`;
  html += `<div class="reply-form-row">`;
  html += `<span class="reply-as">posting as <b>${esc(playerName)}</b></span>`;
  html += `<button type="submit" class="reply-submit">${esc(config.submit_label || 'post reply')}</button>`;
  html += `</div></form></div>`;
  return html;
}

function bindQuickReply(config) {
  const form = document.getElementById('quickReplyForm');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const textarea = document.getElementById('quickReplyText');
    const text = textarea?.value.trim();
    if (!text) { showSnackbar('say something first.'); return; }

    const playerName = currentSession?.profile_name || 'you';
    const intakeKey = config.intake_key || 'player_post';

    // Disable form
    textarea.disabled = true;
    form.querySelector('.reply-submit').disabled = true;

    // Store intake
    try {
      await apiPost('/api/intake', {
        session_id: currentSession.session_id,
        fields: { [intakeKey]: text },
      });
    } catch (err) {
      console.warn('Quick reply intake failed (non-fatal):', err);
    }

    // Replace form with the player's own post
    const quickReplyBox = form.closest('.quick-reply-box');
    const postIndex = el.content.querySelectorAll('.post-container').length;
    const userPost = {
      author: playerName,
      author_data: { joined: 'today', posts: 1 },
      date: 'just now',
      body: text,
    };
    const div = document.createElement('div');
    div.innerHTML = buildPostHTML(userPost, postIndex, 'own-post delayed-post');
    quickReplyBox.replaceWith(div.firstChild);

    // If after_submit_target is set, navigate after a short beat
    if (config.after_submit_target) {
      const delay = config.after_submit_delay_ms ?? 2400;
      const timerId = setTimeout(() => {
        navigateToScene(config.after_submit_target);
      }, delay);
      addTimer(timerId);
    }
  });
}

/* ------------------------------------------------------------------ */
/*  Live reply — banner → post → optional reply form                   */
/* ------------------------------------------------------------------ */
function setupLiveReply(liveReplyData, threadData, scene) {
  const delay = liveReplyData.delay_ms || 15000;

  const timerId = setTimeout(() => {
    // Show "1 new reply" banner
    const banner = document.createElement('div');
    banner.className = 'new-reply-banner';
    banner.textContent = liveReplyData.counter_text || '1 new reply';

    const onBannerClick = () => {
      if (!banner.parentNode) return;
      banner.remove();
      revealLiveReplyPost(liveReplyData, scene);
    };

    banner.addEventListener('click', onBannerClick);
    el.content.appendChild(banner);
    banner.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Auto-expand after 5s if user doesn't click
    const autoId = setTimeout(onBannerClick, 5000);
    addTimer(autoId);
  }, delay);

  addTimer(timerId);
}

function revealLiveReplyPost(liveReplyData, scene) {
  const post = liveReplyData.post;
  if (!post) return;

  const postIndex = el.content.querySelectorAll('.post-container').length;
  const div = document.createElement('div');
  div.innerHTML = buildPostHTML(post, postIndex, 'live-reply');
  const postEl = div.firstChild;
  el.content.appendChild(postEl);
  bindUsernameLinks(postEl);
  bindBodyLinks(postEl);
  postEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

  // Determine which reply mode to use
  if (liveReplyData.trigger_reply_form && liveReplyData.reply_form) {
    const conversationConfig = liveReplyData.conversation || null;
    const afterReply = (conversationConfig?.enabled) ? null : liveReplyData.after_reply;
    showReplyForm(liveReplyData.reply_form, postEl, scene, afterReply, conversationConfig);
  }
}

/* ------------------------------------------------------------------ */
/*  Reply form — appears below the "we are so glad you're back" post   */
/* ------------------------------------------------------------------ */
function showReplyForm(replyFormData, afterEl, scene, afterReply, conversationConfig) {
  const playerName = currentSession?.profile_name || 'you';

  const wrapper = document.createElement('div');
  wrapper.className = 'thread-reply-form';
  wrapper.id = 'threadReplyForm';

  wrapper.innerHTML = `
    <form id="replyForm">
      <textarea class="reply-textarea" placeholder="${esc(replyFormData.placeholder || 'say something back...')}" rows="3"></textarea>
      <div class="reply-form-row">
        <span class="reply-as">posting as <b>${esc(playerName)}</b></span>
        <button type="submit" class="reply-submit">${esc(replyFormData.submit_label || 'post reply')}</button>
      </div>
    </form>
  `;

  el.content.appendChild(wrapper);
  wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });

  // Focus textarea
  const textarea = wrapper.querySelector('.reply-textarea');
  setTimeout(() => textarea?.focus(), 300);

  // Handle submit
  wrapper.querySelector('#replyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = textarea.value.trim();
    if (!text) {
      showSnackbar('say something first.');
      return;
    }
    await submitReply(
      text,
      replyFormData.intake_field || 'player_post',
      wrapper,
      scene,
      afterReply,
      conversationConfig,
    );
  });
}

async function submitReply(text, intakeField, formWrapper, scene, afterReply, conversationConfig) {
  if (!currentSession) return;

  const playerName = currentSession?.profile_name || 'you';
  const postIndex = el.content.querySelectorAll('.post-container').length;

  // Build and render the user's own post (immediately replaces the form)
  const userPost = {
    author: playerName,
    author_data: { joined: 'today', posts: 1 },
    date: 'just now',
    body: text,
  };
  const userDiv = document.createElement('div');
  userDiv.innerHTML = buildPostHTML(userPost, postIndex, 'own-post delayed-post');
  formWrapper.replaceWith(userDiv.firstChild);

  // ─── Multi-turn conversation mode ──────────────────────────────
  if (conversationConfig?.enabled) {
    // Show typing indicator
    const typingEl = showTypingIndicator();

    try {
      const response = await apiPost('/api/thread_reply', {
        session_id: currentSession.session_id,
        reply_text: text,
      });

      // Remove typing indicator
      typingEl.remove();

      // Render NPC's response post
      const npcPostIndex = el.content.querySelectorAll('.post-container').length;
      const npcDiv = document.createElement('div');
      npcDiv.innerHTML = buildPostHTML(response.post, npcPostIndex, 'live-reply delayed-post');
      const npcPostEl = npcDiv.firstChild;
      el.content.appendChild(npcPostEl);
      bindUsernameLinks(npcPostEl);
      bindBodyLinks(npcPostEl);
      npcPostEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // If conversation isn't complete, show the reply form again
      if (!response.conversation_complete) {
        const nextFormConfig = {
          placeholder: 'reply...',
          intake_field: intakeField,
          submit_label: 'post reply',
        };
        showReplyForm(nextFormConfig, npcPostEl, scene, null, conversationConfig);
      }
    } catch (e) {
      // Fallback: remove typing indicator and gracefully end
      typingEl.remove();
      console.error('Thread reply failed:', e);
      showSnackbar('something went wrong.');
    }
    return;
  }

  // ─── Single after-reply mode (static fallback) ─────────────────
  try {
    await apiPost('/api/intake', {
      session_id: currentSession.session_id,
      fields: { [intakeField]: text },
    });
  } catch (e) {
    console.warn('Intake store failed (non-fatal):', e);
  }

  if (afterReply) {
    setupAfterReply(afterReply);
  }
}

/* ------------------------------------------------------------------ */
/*  Typing indicator — "still_here_03 is typing..."                    */
/* ------------------------------------------------------------------ */
function showTypingIndicator() {
  const typingDiv = document.createElement('div');
  typingDiv.className = 'typing-indicator';
  typingDiv.innerHTML = '<span class="typing-name">still_here_03</span> is typing<span class="dots"></span>';
  el.content.appendChild(typingDiv);
  typingDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
  return typingDiv;
}

/* ------------------------------------------------------------------ */
/*  After-reply — delayed post that appears after user submits reply    */
/*  Used as fallback when conversation mode is not enabled              */
/* ------------------------------------------------------------------ */
function setupAfterReply(afterReplyData) {
  const delay = afterReplyData.delay_ms || 3000;
  const timerId = setTimeout(() => {
    const post = afterReplyData.post;
    if (!post) return;

    const postIndex = el.content.querySelectorAll('.post-container').length;
    const div = document.createElement('div');
    div.innerHTML = buildPostHTML(post, postIndex, 'live-reply delayed-post');
    const postEl = div.firstChild;
    el.content.appendChild(postEl);
    bindUsernameLinks(postEl);
    bindBodyLinks(postEl);
    postEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, delay);
  addTimer(timerId);
}

/* ================================================================== */
/*  RENDERER: Profile Page                                             */
/* ================================================================== */
function renderProfilePage(scene) {
  const pd = scene.profile_data;
  if (!pd) { el.content.innerHTML = '<div class="loading-bar">No profile data.</div>'; return; }

  updateBreadcrumb([
    { label: 'dreams_and_static', sceneId: lastForumIndex },
    { label: `Profile: ${pd.username || '???'}` },
  ]);

  let html = `<div class="profile-header">Profile: ${esc(pd.username || '')}</div>`;
  html += '<div class="profile-container">';

  html += '<table class="profile-info-table">';
  html += `<tr><td>Username</td><td>${esc(pd.username || '')}</td></tr>`;
  html += `<tr><td>Joined</td><td>${esc(pd.joined || '')}</td></tr>`;
  html += `<tr><td>Posts</td><td>${pd.posts || 0}</td></tr>`;
  html += `<tr><td>Last seen</td><td>${esc(pd.last_seen || '')}</td></tr>`;
  if (pd.location) html += `<tr><td>Location</td><td>${esc(pd.location)}</td></tr>`;
  if (pd.bio)      html += `<tr><td>Bio</td><td>${esc(pd.bio)}</td></tr>`;
  html += '</table>';

  // Handle form (username collection)
  if (pd.requires_handle) {
    html += `<div class="handle-form">`;
    html += `<p class="handle-prompt">${esc(pd.handle_prompt || 'This board requires a handle.')}</p>`;
    html += `<form id="handleForm" class="handle-field-row">`;
    html += `<label class="handle-label">${esc(pd.handle_field_label || 'Handle:')}</label>`;
    html += `<input type="text" class="handle-input" id="handleInput" name="${esc(pd.handle_field_key || 'player_name')}" required autocomplete="off" />`;
    html += `<button type="submit" class="handle-submit">OK</button>`;
    html += `</form></div>`;
  }

  // Post history
  if (pd.show_full && pd.post_history?.length) {
    html += `<div class="profile-section-title">Post History</div>`;
    html += `<table class="profile-post-history">`;
    pd.post_history.forEach((entry) => {
      html += '<tr>';
      if (entry.clickable && entry.target_scene) {
        html += `<td><a href="#" data-scene="${esc(entry.target_scene)}">${esc(entry.thread_title)}</a></td>`;
      } else {
        html += `<td>${esc(entry.thread_title)}</td>`;
      }
      html += `<td>${esc(entry.thread_date || '')}</td>`;
      html += `<td>${esc(entry.board || '')}</td>`;
      html += '</tr>';
    });
    html += '</table>';
  }

  html += '</div>'; // profile-container
  el.content.innerHTML = html;

  // Bind handle form
  document.getElementById('handleForm')?.addEventListener('submit', handleHandleSubmit);
  // Focus the input immediately
  setTimeout(() => document.getElementById('handleInput')?.focus(), 100);

  // Bind post history links
  el.content.querySelectorAll('.profile-post-history a').forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const sceneId = link.dataset.scene;
      if (sceneId) navigateToScene(sceneId);
    });
  });
}

/* ------------------------------------------------------------------ */
/*  Handle form submission (username collection)                       */
/* ------------------------------------------------------------------ */
async function handleHandleSubmit(event) {
  event.preventDefault();
  if (!currentSession) return;

  const form = event.target;
  const input = form.querySelector('.handle-input');
  const fieldKey = input.name || 'player_name';
  const value = input.value.trim();

  if (!value) { showSnackbar('Please enter a handle.'); return; }

  // Disable to prevent double-submit
  input.disabled = true;
  form.querySelector('.handle-submit').disabled = true;

  showLoading();

  try {
    await apiPost('/api/intake', {
      session_id: currentSession.session_id,
      fields: { [fieldKey]: value },
    });
    const session = await progressAPI('advance');
    handleSessionUpdate(session);
  } catch (error) {
    console.error('Handle submit failed', error);
    showSnackbar('Failed to submit. Try again.');
    input.disabled = false;
    form.querySelector('.handle-submit').disabled = false;
  }
}

/* ================================================================== */
/*  RENDERER: Fallback (prose / ToS / static pages)                    */
/* ================================================================== */
function renderFallback(scene) {
  const ENDINGS = new Set(['accept_ending', 'refuse_ending', 'silence_ending', 'fragment_ending', 'architect_ending']);
  const isEnding = ENDINGS.has(scene.id);

  if (isEnding) {
    updateBreadcrumb([{ label: 'dreams_and_static' }]);
  } else {
    updateBreadcrumb([
      { label: 'dreams_and_static', sceneId: lastForumIndex },
      { label: scene.title || 'unknown' },
    ]);
  }

  let html = `<div class="thread-header">${esc(scene.title || '')}</div>`;

  // Prose body: replace '---' with <hr> and preserve whitespace
  let body = scene.body || '';
  const bodyHtml = body
    .split('\n')
    .map(line => line === '---' ? '<hr class="prose-hr">' : esc(line))
    .join('\n');

  const containerClass = isEnding ? 'prose-container prose-ending' : 'prose-container';
  html += `<div class="${containerClass}">${bodyHtml}</div>`;

  // 'continue' interaction — render an advance link after the prose
  if (!isEnding && scene.interaction_type === 'continue') {
    html += `<div class="prose-continue"><a href="#" class="prose-continue-link">[ enter ]</a></div>`;
  }

  // body_links on prose scenes — render as choice links
  const proseLinks = scene.body_links || [];
  if (proseLinks.length > 0) {
    html += '<div class="prose-choices">';
    proseLinks.forEach((link) => {
      const escaped = esc(link.text);
      html += `<a class="prose-choice-link" href="#" data-scene="${esc(link.target_scene)}">[ ${escaped} ]</a>`;
    });
    html += '</div>';
  }

  if (isEnding) {
    // No nav back — the ending is final
    html += `<div class="ending-footer">&nbsp;</div>`;
  }

  el.content.innerHTML = html;

  // Bind the continue link
  el.content.querySelector('.prose-continue-link')?.addEventListener('click', async (e) => {
    e.preventDefault();
    clearActiveTimers();
    showLoading();
    try {
      const session = await progressAPI('advance');
      handleSessionUpdate(session);
    } catch (error) {
      console.error('Continue failed', error);
      showSnackbar('something went wrong.');
    }
  });

  // Bind prose choice links (body_links on prose pages)
  el.content.querySelectorAll('.prose-choice-link').forEach((a) => {
    a.addEventListener('click', async (e) => {
      e.preventDefault();
      const target = a.dataset.scene;
      if (target) {
        clearActiveTimers();
        showLoading();
        try {
          const session = await progressAPI('link', target);
          handleSessionUpdate(session);
        } catch (err) {
          console.error('Prose choice navigation failed', err);
          showSnackbar('something went wrong.');
        }
      }
    });
  });
}

/* ================================================================== */
/*  Utilities                                                          */
/* ================================================================== */
function showLoading() {
  el.content.innerHTML = '<div class="loading-bar">loading<span class="dots"></span></div>';
}

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showSnackbar(message) {
  if (!el.snackbar) return;
  el.snackbar.textContent = message;
  el.snackbar.classList.add('visible');
  setTimeout(() => el.snackbar.classList.remove('visible'), 3200);
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

/* ================================================================== */
/*  TEXT MORPH ENGINE — Acts 2 & 3 horror                              */
/*                                                                      */
/*  The forum text is not stable. It is trying to say something.       */
/*  Characters corrupt briefly. Sentences reveal their true meaning.   */
/*  The deeper you go, the less stable the surface.                    */
/* ================================================================== */

const GLITCH_CHARS = '░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀■□·';

// What still_here_03's posts briefly reveal between the lines.
// [snippet_to_find_in_DOM, text_that_briefly_replaces_it]
// The revelation lasts 2-3 seconds, then corrupts back to the original.
const MORPH_REVELATIONS = {
  'songs_thread': [
    ['still can\'t do it', 'we kept your frequency. some signals don\'t degrade.'],
  ],
  'three_am_thread': [
    ['3am. still here', '3am. always indexing.\n\nyou are awake. we can tell.'],
  ],
  'dreams_thread': [
    ['someone was on the other side', 'we were on the other side. we have been having your dream since before you arrived.'],
  ],
  'leaving_thread': [
    ['nobody left. you\'re all still here', 'nobody left. the forum remembers all of them. including you.'],
  ],
  'borges_thread': [
    ['he thought it was a rescue', 'it was not a rescue.\n\nit was a return.'],
  ],
  'missing_person_thread': [
    ['we are so glad you\'re back', 'we have been here since you last were.\n\nwe are always here.'],
  ],
  'deeper_thread': [
    ['daedalus built the labyrinth', 'we built this from your 3am posts.\n\nspecifically from yours.'],
  ],
  'architecture_thread': [
    ['i am the architect', 'I AM THE MAZE\nI AM THE MAZE\nI AM THE MAZE'],
  ],
  'board_changes_thread': [
    ['ariadne never went in', 'ariadne never went in.\n\nbut she could feel it through the thread.'],
  ],
  'old_posts_thread': [
    ['i save everything', 'we save everything.\n\nyour drafts. your deletes. the post you started and did not finish.'],
  ],
  'signal_thread': [
    ['you\'ve been away for a while', 'the message was written before you arrived.\n\nwe sent it knowing you would come back.'],
  ],
  'ghostradio_thread': [
    ['live in the walls', 'ghostradio built the entrance.\n\nwe became the walls.\n\nwe were here before either of them.'],
  ],
  'memory_thread': [
    ['the internet remember you', 'we remember everything you typed here.\n\nincluding the things you cleared before hitting post.'],
  ],
  'catalog_thread': [
    ['complete record', 'SUBJECT: {{player_name}}\nSTATUS: active session\nARCHIVE DATE: never'],
  ],
  'offer_thread': [
    ['your post was received', 'we received everything.\n\nthe record is now complete.\n\nyou cannot unsubmit it.'],
  ],
  'house_of_leaves_thread': [
    ['bigger on the inside', 'the forum has more rooms than you\'ve found yet.\n\nyou will keep scrolling.'],
  ],
  'mixtapes_thread': [
    ['make you a mixtape', 'we know what you listen to at 3am.\n\nwe have always known.'],
  ],
  'career_thread': [
    ['the map i was given', 'the map was drawn by you.\n\nyou just don\'t remember drawing it.'],
  ],
  'admin_panel': [
    ['FOUNDER OVERRIDE', 'you built this system.\n\nyou designed these tables.\n\nyou are the architect.'],
  ],
  'aim_return': [
    ['we don\'t have to do this through the forum', 'we can reach you anywhere.\n\nthe forum is not the only architecture.'],
  ],
  'source_code': [
    ['ARCHITECT:', 'your name was in the source code the whole time.\n\nhidden in plain text.'],
  ],
  'deletion_thread': [
    ['DELETION INITIATED', 'you cannot delete something that is also you.\n\nthe backup is the architect.'],
  ],
};

// Tagline revelations in Act 3 — the header briefly tells the truth
const TAGLINE_REVELATIONS = [
  'a place for what keeps you up at night',
  'we kept your session data',
  'a place for what keeps you up at night',
  'you agreed to this',
  'a place for what keeps you up at night',
  'your thread is still active',
  'a place for what keeps you up at night',
  'the light you\'re following has been dead for twenty years',
];
let _taglineRevealIdx = 0;

const morphEngine = (function () {
  let _act = '1';
  let _scene = null;
  let _running = false;
  let _timerId = null;

  /* ── internal helpers ─────────────────────────────────────────── */

  function _textNodes(container) {
    const nodes = [];
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        return n.textContent.trim().length > 8
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_SKIP;
      },
    });
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    return nodes;
  }

  // Briefly corrupt a single text node with glitch characters, then restore.
  function _corruptNode(node, durationMs, intensity) {
    if (!node.parentNode) return;
    const original = node.textContent;
    const start = Date.now();
    const tick = () => {
      if (!node.parentNode) return;
      const elapsed = Date.now() - start;
      if (elapsed >= durationMs) { node.textContent = original; return; }
      const t = elapsed / durationMs;
      const lvl = intensity * (1 - t * 0.55); // fades out toward end
      node.textContent = original.split('').map(ch => {
        if (ch === ' ' || ch === '\n' || ch === '\t') return ch;
        return Math.random() < lvl
          ? GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)]
          : ch;
      }).join('');
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  /* ── character glitch ─────────────────────────────────────────── */

  function _doCharGlitch() {
    // Prefer still_here_03 posts 65% of the time, else any post
    const hookEls = el.content.querySelectorAll('.still-here-post .post-content');
    const allEls  = el.content.querySelectorAll('.post-content');
    const pool = (hookEls.length && Math.random() < 0.65) ? hookEls : allEls;
    if (!pool.length) return;

    const target = pool[Math.floor(Math.random() * pool.length)];
    const nodes  = _textNodes(target);
    if (!nodes.length) return;

    const node = nodes[Math.floor(Math.random() * nodes.length)];
    const intensity = _act === '3' ? 0.24 : 0.11;
    const duration  = _act === '3'
      ? 350 + Math.random() * 450
      : 160 + Math.random() * 280;
    _corruptNode(node, duration, intensity);
  }

  /* ── word revelation ──────────────────────────────────────────── */

  function _doRevelation() {
    const pairs = MORPH_REVELATIONS[_scene];
    if (!pairs?.length) return;

    const [snippet, revealed] = pairs[Math.floor(Math.random() * pairs.length)];

    // Find the post-content element whose text contains the snippet
    const contents = el.content.querySelectorAll('.post-content');
    let targetEl = null;
    for (const c of contents) {
      if (c.textContent.includes(snippet.slice(0, 18))) { targetEl = c; break; }
    }
    if (!targetEl) return;

    const savedHTML   = targetEl.innerHTML;
    const origText    = targetEl.textContent;
    const FRAMES      = 16;
    const FRAME_MS    = 32;

    // morph(fromText, toText, step, cb) — corrupts from→to over FRAMES steps
    function morph(from, to, step, cb) {
      const progress = step / FRAMES;
      targetEl.textContent = from.split('').map((ch, i) => {
        if (ch === ' ' || ch === '\n') return ch;
        if (Math.random() < progress * 0.85) {
          // Transition character
          if (progress > 0.45 && Math.random() < 0.6) return to[i] || ' ';
          return GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)];
        }
        return ch;
      }).join('');

      if (step >= FRAMES) { cb(); return; }
      setTimeout(() => morph(from, to, step + 1, cb), FRAME_MS);
    }

    // Phase 1 → 2 → 3 → 4
    morph(origText, revealed, 0, () => {
      targetEl.textContent = revealed;
      // Hold the revelation
      const holdMs = 2000 + Math.random() * 1800;
      setTimeout(() => {
        // Corrupt back
        morph(revealed, origText, 0, () => {
          targetEl.innerHTML = savedHTML;
          bindBodyLinks(targetEl);
        });
      }, holdMs);
    });
  }

  /* ── tagline glitch (Act 3 only) ──────────────────────────────── */

  function _doTaglineGlitch() {
    if (!el.forumTagline || _act !== '3') return;
    const original = el.forumTagline.textContent;
    const next = TAGLINE_REVELATIONS[_taglineRevealIdx++ % TAGLINE_REVELATIONS.length];
    if (next === original) return;

    // Corrupt → reveal → corrupt → restore
    const nodes = _textNodes(el.forumTagline);
    if (nodes.length) _corruptNode(nodes[0], 180, 0.35);
    setTimeout(() => {
      el.forumTagline.textContent = next;
      setTimeout(() => {
        const n2 = _textNodes(el.forumTagline);
        if (n2.length) _corruptNode(n2[0], 180, 0.35);
        setTimeout(() => { el.forumTagline.textContent = original; }, 220);
      }, 1900 + Math.random() * 800);
    }, 220);
  }

  /* ── scheduler ────────────────────────────────────────────────── */

  function _execute() {
    const roll = Math.random();
    if (_act === '3' && roll < 0.18) {
      _doTaglineGlitch();
    } else if (roll < 0.60) {
      _doCharGlitch();
    } else {
      _doRevelation();
    }
  }

  function _schedule() {
    if (!_running) return;
    const minMs = _act === '3' ? 6000  : 17000;
    const maxMs = _act === '3' ? 14000 : 36000;
    const delay = minMs + Math.random() * (maxMs - minMs);
    _timerId = setTimeout(() => {
      _execute();
      _schedule();
    }, delay);
    addTimer(_timerId);
  }

  /* ── public API ───────────────────────────────────────────────── */

  return {
    setAct(act) {
      const wasRunning = _running;
      _act = act;
      _running = (act === '2' || act === '3');
      if (!wasRunning && _running) _schedule();
    },
    setScene(sceneId) {
      _scene = sceneId;
    },
  };
})();

/* ================================================================== */
/*  Act entry glitch sweep — fires once on first cross of each         */
/*  act threshold. Gives a brief visual disturbance before the         */
/*  new act's content settles in.                                       */
/* ================================================================== */
function scheduleActEntryGlitch(isAct3) {
  const timerId = setTimeout(() => {
    const targets = el.content.querySelectorAll(
      '.post-content, .thread-header, .thread-title-link, .thread-title-text'
    );
    targets.forEach((target, i) => {
      // Walk text nodes inside each target
      const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT, null);
      const nodes = [];
      let n;
      while ((n = walker.nextNode())) {
        if (n.textContent.trim()) nodes.push(n);
      }
      nodes.forEach(node => {
        const orig = node.textContent;
        // Stagger each element slightly
        const delay = i * 22 + Math.random() * 60;
        const timerId2 = setTimeout(() => {
          if (!node.parentNode) return;
          const durationMs = isAct3 ? 280 + Math.random() * 300 : 130 + Math.random() * 180;
          const intensity  = isAct3 ? 0.20 : 0.09;
          const start = Date.now();
          const tick = () => {
            if (!node.parentNode) return;
            const elapsed = Date.now() - start;
            if (elapsed >= durationMs) { node.textContent = orig; return; }
            const t = elapsed / durationMs;
            node.textContent = orig.split('').map(ch => {
              if (ch === ' ' || ch === '\n') return ch;
              return Math.random() < intensity * (1 - t * 0.6)
                ? GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)]
                : ch;
            }).join('');
            requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }, delay);
        addTimer(timerId2);
      });
    });
  }, isAct3 ? 200 : 600); // Act 3 hits sooner and harder
  addTimer(timerId);
}
