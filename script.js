const STORAGE_KEY = 'deadlightProfile';
const orientationSupported =
  typeof window !== 'undefined' && 'DeviceOrientationEvent' in window;
const requiresOrientationPermission =
  orientationSupported &&
  typeof window.DeviceOrientationEvent?.requestPermission === 'function';

const bootScreen = document.getElementById('bootScreen');
const bootLog = document.getElementById('bootLog');
const appRoot = document.getElementById('appRoot');
const connectionStatusEl = document.getElementById('connectionStatus');
const storyWindow = document.getElementById('storyWindow');
const storyContent = document.getElementById('storyContent');
const hudMessageEl = document.getElementById('hudMessage');
const tiltHint = document.getElementById('tiltHint');
const loadingIndicator = document.getElementById('loadingIndicator');
const tiltBarLeft = document.getElementById('tiltBarLeft');
const tiltBarRight = document.getElementById('tiltBarRight');
const registerOverlay = document.getElementById('registerOverlay');
const registerForm = document.getElementById('registerForm');
const registerNameInput = document.getElementById('registerName');
const registerEmailInput = document.getElementById('registerEmail');
const registerTriggerBtn = document.getElementById('registerTriggerBtn');
const registerCloseBtn = document.getElementById('registerCloseBtn');

const bootSequence = [
  '[MODEM] INITIALIZING 56K HANDSHAKE...',
  '[OS] LOADING DEADLIGHT SHELL V3.3 (2003 BUILD)',
  '[SCAN] SEARCHING FOR OFFSITE NODE...',
  '[LINK] TUNNEL ESTABLISHED : LATENCY UNSTABLE',
  '[AUTH] CONTRACTOR ID ACCEPTED',
  '[SYS] MAZE CORRIDOR LOCKED // AWAITING USER',
];

let sessionId = null;
let paragraphCount = 0;
let profile = loadProfile();
let autoAdvancePending = false;
let storyComplete = false;
let registrationAvailable = false;
let registrationShown = false;

const paragraphState = new Map();
let activeBranch = null;
let branchElement = null;
let branchResolving = false;
let orientationListener = null;
let orientationPermissionGranted = !requiresOrientationPermission;
let decisionDirection = null;
let decisionTimer = null;
let currentFocusedElement = null;
let tiltGlowTimeout = null;
let lastScrollPosition = 0;
let mutationTimeout = null;
let deviceOrientation = { gamma: 0, beta: 0 };
const MUTATION_CHANCE = 0.15; // 15% chance of mutation per paragraph
const MUTATION_DELAY = 300; // Time before mutation starts after scrolling past

async function requestOrientationPermission() {
  // Add debug logging
  console.log('Requesting orientation permission...');
  console.log('Requires permission:', requiresOrientationPermission);
  console.log('Orientation supported:', orientationSupported);
  
  if (!requiresOrientationPermission) {
    console.log('No permission required, enabled by default');
    return true;
  }
  
  try {
    // On iOS, need to wait for user interaction
    const enableTiltBtn = document.createElement('button');
    enableTiltBtn.textContent = 'Enable Tilt Controls';
    enableTiltBtn.className = 'enable-tilt-btn';
    document.body.appendChild(enableTiltBtn);
    
    await new Promise((resolve) => {
      enableTiltBtn.addEventListener('click', async () => {
        const permission = await DeviceOrientationEvent.requestPermission();
        console.log('Permission result:', permission);
        orientationPermissionGranted = permission === 'granted';
        enableTiltBtn.remove();
        resolve(orientationPermissionGranted);
      });
    });
    
    return orientationPermissionGranted;
  } catch (err) {
    console.error('Failed to request orientation permission:', err);
    return false;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  prefillProfile();
  await runBootSequence();
  
  // Request device orientation permission if needed
  if (orientationSupported) {
    const granted = await requestOrientationPermission();
    if (granted) {
      tiltHint.classList.remove('hidden');
      setTimeout(() => {
        tiltHint.classList.add('hidden');
      }, 5000);
    }
  }
  
  launchApp();
  startSession();
});

storyWindow.addEventListener('scroll', handleStoryScroll);

// Handle device orientation changes
window.addEventListener('deviceorientation', (event) => {
  if (!orientationPermissionGranted) return;
  
  deviceOrientation = {
    gamma: event.gamma || 0, // Left/Right tilt (-90 to 90)
    beta: event.beta || 0    // Forward/Back tilt (-180 to 180)
  };
  
  // Update tilt bars
  const maxTilt = 30;
  const leftTilt = Math.max(-maxTilt, Math.min(maxTilt, -deviceOrientation.gamma));
  const rightTilt = Math.max(-maxTilt, Math.min(maxTilt, deviceOrientation.gamma));
  
  tiltBarLeft.style.height = `${(leftTilt + maxTilt) / (maxTilt * 2) * 100}%`;
  tiltBarRight.style.height = `${(rightTilt + maxTilt) / (maxTilt * 2) * 100}%`;
  
  // Handle navigation based on tilt
  handleTiltNavigation();
});

window.addEventListener(
  'wheel',
  (event) => {
    if (appRoot.classList.contains('hidden')) {
      return;
    }
    // keep desktop users moving even when the body captures the wheel event
    event.preventDefault();
    storyWindow.scrollBy({ top: event.deltaY, behavior: 'auto' });
    handleStoryScroll();
  },
  { passive: false },
);

window.addEventListener('keydown', (event) => {
  if (appRoot.classList.contains('hidden')) {
    return;
  }
  const key = event.key.toLowerCase();
  if (['arrowdown', 's', 'pagedown', ' '].includes(key)) {
    event.preventDefault();
    storyWindow.scrollBy({ top: 160, behavior: 'smooth' });
    handleStoryScroll();
    return;
  }
  if (['arrowup', 'w', 'pageup'].includes(key)) {
    event.preventDefault();
    storyWindow.scrollBy({ top: -160, behavior: 'smooth' });
    handleStoryScroll();
    return;
  }
  if (key === 'r') {
    event.preventDefault();
    showRegistration();
  }
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!sessionId) {
    return;
  }
  const name = registerNameInput.value.trim();
  const email = registerEmailInput.value.trim();
  if (!name || !email) {
    setHudMessage('NAME + EMAIL REQUIRED TO UNLOCK THE DOOR.');
    return;
  }
  try {
    const response = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, session_id: sessionId }),
    });
    if (!response.ok) {
      throw new Error('Registration failed');
    }
    profile = { name, email };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
    registerOverlay.classList.add('hidden');
    setHudMessage('REGISTRATION CAPTURED. MAZE WILL CALL WHEN IT SHIFTS.');
    updateRegistrationUI();
  } catch (err) {
    setHudMessage('REGISTRATION FAILED. TRY AGAIN ON THE NEXT LOOP.');
  }
});

if (registerTriggerBtn) {
  registerTriggerBtn.addEventListener('click', () => {
    showRegistration();
  });
}

if (registerCloseBtn) {
  registerCloseBtn.addEventListener('click', () => {
    registerOverlay.classList.add('hidden');
    setHudMessage('REGISTER LATER. THE CORRIDOR IS STILL SHUFFLING.');
  });
}

function runBootSequence() {
  return new Promise((resolve) => {
    let index = 0;
    const tick = () => {
      if (index >= bootSequence.length) {
        setTimeout(resolve, 480);
        return;
      }
      appendBootLine(bootSequence[index]);
      index += 1;
      setTimeout(tick, 420 + Math.random() * 260);
    };
    tick();
  });
}

function appendBootLine(line) {
  const wrapper = document.createElement('div');
  wrapper.className = 'boot-line';
  const cursor = document.createElement('span');
  cursor.className = 'cursor';
  cursor.textContent = '>';
  const text = document.createElement('span');
  text.textContent = line;
  wrapper.append(cursor, text);
  bootLog.appendChild(wrapper);
  bootLog.scrollTop = bootLog.scrollHeight;
}

function launchApp() {
  bootScreen.classList.add('hidden');
  appRoot.classList.remove('hidden');
  connectionStatusEl.textContent = 'LINKED';
}

function handleTiltNavigation() {
  if (branchResolving || autoAdvancePending) return;
  
  const { gamma, beta } = deviceOrientation;
  const tiltThreshold = 20; // Degrees of tilt required to trigger navigation
  
  // Clear any existing decision timer
  if (decisionTimer) {
    clearTimeout(decisionTimer);
    decisionTimer = null;
  }
  
  // Handle left/right choices with gamma (side-to-side tilt)
  if (Math.abs(gamma) > tiltThreshold) {
    decisionDirection = gamma > 0 ? 'right' : 'left';
    if (activeBranch) {
      decisionTimer = setTimeout(() => {
        resolveBranch(decisionDirection);
      }, 1000);
    }
  }
  
  // Handle forward/backward navigation with beta (forward/back tilt)
  if (Math.abs(beta - 45) > tiltThreshold) { // 45° is the "neutral" position
    const scrollAmount = (beta - 45) > 0 ? 160 : -160;
    storyWindow.scrollBy({ top: scrollAmount, behavior: 'smooth' });
  }
}

function checkForMutations() {
  const paragraphs = document.querySelectorAll('.story-paragraph');
  const scrollPosition = storyWindow.scrollTop;
  const windowHeight = storyWindow.clientHeight;
  
  paragraphs.forEach((paragraph) => {
    const rect = paragraph.getBoundingClientRect();
    const isPastParagraph = rect.bottom < windowHeight * 0.3; // 30% from top
    
    if (isPastParagraph && !paragraph.classList.contains('past')) {
      paragraph.classList.add('past');
      
      // Random chance to trigger mutation
      if (Math.random() < MUTATION_CHANCE) {
        setTimeout(() => {
          triggerMutation(paragraph);
        }, MUTATION_DELAY);
      }
    }
  });
}

function triggerMutation(paragraph) {
  if (paragraph.classList.contains('mutating')) return;
  
  paragraph.classList.add('mutating');
  
  // Store original text
  const originalText = paragraph.textContent;
  
  // Create glitch text
  const glitchText = originalText
    .split('')
    .map(char => {
      if (Math.random() < 0.3) { // 30% chance to corrupt each character
        return '█▓▒░'[Math.floor(Math.random() * 4)];
      }
      return char;
    })
    .join('');
  
  // Apply glitch effect
  paragraph.textContent = glitchText;
  
  // Restore original text after animation
  setTimeout(() => {
    paragraph.textContent = originalText;
    paragraph.classList.remove('mutating');
  }, 1000);
}

function showLoading() {
  loadingIndicator.classList.remove('hidden');
}

function hideLoading() {
  loadingIndicator.classList.add('hidden');
}

async function startSession() {
  registrationAvailable = false;
  registrationShown = false;
  if (registerOverlay) {
    registerOverlay.classList.add('hidden');
  }
  updateRegistrationUI();
  showLoading();
  try {
    const response = await fetch('/api/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_name: profile?.name ?? null,
      }),
    });
    if (!response.ok) {
      throw new Error('Failed to start session');
    }
    const payload = await response.json();
    sessionId = payload.session_id;
    renderPayload(payload, { autoScroll: true });
  } catch (err) {
    setHudMessage('CONNECTION LOST. REFRESH TO RETRY.');
  }
}

function renderPayload(payload, { autoScroll = false } = {}) {
  if (!payload) {
    return;
  }
  if (typeof payload.allow_registration === 'boolean') {
    registrationAvailable = payload.allow_registration;
  }
  if (payload.paragraphs?.length) {
    payload.paragraphs.forEach((paragraph) => appendParagraph(paragraph));
  }
  if (payload.branch) {
    activateBranch(payload.branch);
  } else if (!payload.branch && activeBranch) {
    deactivateBranch();
  }
  if (typeof payload.prompt_scroll_back === 'boolean' && payload.prompt_scroll_back) {
    setHudMessage('THE MAZE WHISPERS: SCROLL BACK. SOMETHING MOVED.');
  } else if (payload.hud_message) {
    setHudMessage(payload.hud_message);
  }
  if (payload.unlock_registration) {
    registrationAvailable = true;
    updateRegistrationUI();
    if (!registrationShown) {
      setHudMessage('REGISTRATION READY. PRESS R OR CLICK REGISTER WHEN YOU WANT OUT.');
    }
  }
  if (typeof payload.story_complete === 'boolean') {
    storyComplete = payload.story_complete;
  }
  if (autoScroll && isNearBottom()) {
    scrollToBottom();
  }
  updateParagraphStates();
}

function appendParagraph(paragraph) {
  const article = document.createElement('article');
  article.className = 'story-paragraph';
  article.dataset.paragraphId = paragraph.id;
  paragraphCount += 1;
  article.dataset.index = `P${String(paragraphCount).padStart(2, '0')}`;
  article.textContent = paragraph.text;
  article.addEventListener('pointerenter', () => {
    article.classList.add('is-hover');
  });
  article.addEventListener('pointerleave', () => {
    article.classList.remove('is-hover');
  });
  storyContent.appendChild(article);
  paragraphState.set(paragraph.id, {
    element: article,
    mutations: Array.isArray(paragraph.mutations) ? [...paragraph.mutations] : [],
    justMutated: false,
    mutating: false,
  });
}

function activateBranch(branch) {
  deactivateBranch();
  activeBranch = branch;
  branchElement = document.createElement('section');
  branchElement.className = 'branch-node';
  branchElement.dataset.branchId = branch.id;

  if (branch.instruction) {
    const instruction = document.createElement('p');
    instruction.className = 'tilt-instruction';
    instruction.textContent = `${branch.instruction} (Tap, arrow keys, or tilt.)`;
    branchElement.appendChild(instruction);
  }

  const optionsWrapper = document.createElement('div');
  optionsWrapper.className = 'branch-options';
  branch.options.forEach((option) => {
    const optionEl = document.createElement('div');
    optionEl.className = 'branch-option';
    optionEl.dataset.direction = option.direction;
    const labelEl = document.createElement('div');
    labelEl.className = 'option-label';
    labelEl.textContent = option.label;
    const bodyEl = document.createElement('div');
    bodyEl.className = 'option-body';
    bodyEl.textContent = option.body;
    optionEl.append(labelEl, bodyEl);
    optionEl.addEventListener('click', () => {
      submitDecision(option.direction, { via: 'tap' });
    });
    optionsWrapper.appendChild(optionEl);
  });
  branchElement.appendChild(optionsWrapper);

  if (requiresOrientationPermission && !orientationPermissionGranted) {
    const permissionBtn = document.createElement('button');
    permissionBtn.type = 'button';
    permissionBtn.textContent = 'ENABLE TILT CONTROLS';
    permissionBtn.addEventListener('click', async () => {
      await requestOrientationPermission();
    });
    branchElement.appendChild(permissionBtn);
  }

  storyContent.appendChild(branchElement);
  tiltHint.classList.remove('hidden');
  window.addEventListener('keydown', handleDecisionKeys);
  startOrientationListener();
  setHudMessage('LEAN OR USE ARROWS TO CHOOSE. CLICK IF THE MAZE STALLS.');
  setTimeout(() => {
    branchElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 80);
}

function deactivateBranch() {
  stopOrientationListener();
  tiltHint.classList.add('hidden');
  window.removeEventListener('keydown', handleDecisionKeys);
  activeBranch = null;
  decisionDirection = null;
  clearDecisionTimer();
  if (branchElement) {
    branchElement.remove();
    branchElement = null;
  }
  resetTiltBars();
  pulseCurrentParagraph(false);
}

function handleDecisionKeys(event) {
  if (!activeBranch || branchResolving) {
    return;
  }
  if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'a') {
    submitDecision('left', { via: 'key' });
  } else if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'd') {
    submitDecision('right', { via: 'key' });
  }
}

async function requestOrientationPermission() {
  if (!requiresOrientationPermission) {
    orientationPermissionGranted = true;
    startOrientationListener();
    return;
  }
  try {
    const result = await window.DeviceOrientationEvent.requestPermission();
    orientationPermissionGranted = result === 'granted';
    if (orientationPermissionGranted) {
      startOrientationListener();
      setHudMessage('TILT ENABLED. THE MAZE IS LISTENING.');
      if (branchElement) {
        const button = branchElement.querySelector('button');
        if (button) {
          button.remove();
        }
      }
    } else {
      setHudMessage('TILT DENIED. USE TAP OR ARROW KEYS TO CHOOSE.');
    }
  } catch (err) {
    setHudMessage('TILT REQUEST FAILED. TAP OR USE KEYS TO CHOOSE.');
  }
}

function startOrientationListener() {
  if (!orientationSupported || !activeBranch) {
    return;
  }
  if (requiresOrientationPermission && !orientationPermissionGranted) {
    return;
  }
  if (orientationListener) {
    window.removeEventListener('deviceorientation', orientationListener);
  }
  orientationListener = (event) => {
    if (!activeBranch || branchResolving) {
      return;
    }
    const gamma = typeof event.gamma === 'number' ? event.gamma : 0;
    updateTiltBars(gamma);
    const direction =
      gamma <= -12 ? 'left' : gamma >= 12 ? 'right' : null;
    if (!direction) {
      clearDecisionTimer();
      highlightBranchOption(null);
      pulseCurrentParagraph(false);
      return;
    }
    highlightBranchOption(direction);
    pulseCurrentParagraph(true);
    if (decisionDirection !== direction) {
      clearDecisionTimer();
      decisionDirection = direction;
      const strength = Math.min(Math.abs(gamma) / 25, 1);
      decisionTimer = setTimeout(() => {
        submitDecision(direction, {
          via: 'tilt',
          confidence: strength,
        });
      }, 600);
    }
  };
  window.addEventListener('deviceorientation', orientationListener);
}

function stopOrientationListener() {
  if (orientationListener) {
    window.removeEventListener('deviceorientation', orientationListener);
    orientationListener = null;
  }
}

function highlightBranchOption(direction) {
  if (!branchElement) {
    return;
  }
  const options = branchElement.querySelectorAll('.branch-option');
  options.forEach((option) => {
    if (direction && option.dataset.direction === direction) {
      option.classList.add('is-active');
    } else {
      option.classList.remove('is-active');
    }
  });
}

function resetTiltBars() {
  tiltBarLeft.classList.remove('is-filled');
  tiltBarRight.classList.remove('is-filled');
  tiltBarLeft.style.setProperty('--fill', '0');
  tiltBarRight.style.setProperty('--fill', '0');
}

function updateTiltBars(gamma) {
  if (!tiltHint || !tiltBarLeft || !tiltBarRight) {
    return;
  }
  const normalized = Math.min(Math.abs(gamma) / 18, 1);
  if (gamma < -8) {
    tiltBarLeft.style.setProperty('--fill', normalized.toFixed(2));
    tiltBarRight.style.setProperty('--fill', '0');
    if (normalized > 0.6) {
      tiltBarLeft.classList.add('is-filled');
    } else {
      tiltBarLeft.classList.remove('is-filled');
    }
    tiltBarRight.classList.remove('is-filled');
  } else if (gamma > 8) {
    tiltBarRight.style.setProperty('--fill', normalized.toFixed(2));
    tiltBarLeft.style.setProperty('--fill', '0');
    if (normalized > 0.6) {
      tiltBarRight.classList.add('is-filled');
    } else {
      tiltBarRight.classList.remove('is-filled');
    }
    tiltBarLeft.classList.remove('is-filled');
  } else {
    resetTiltBars();
  }
}

function clearDecisionTimer() {
  decisionDirection = null;
  if (decisionTimer) {
    clearTimeout(decisionTimer);
    decisionTimer = null;
  }
}

async function submitDecision(direction, meta = {}) {
  if (!activeBranch || branchResolving || !sessionId) {
    return;
  }
  branchResolving = true;
  highlightBranchOption(direction);
  pulseCurrentParagraph(true);
  setHudMessage(
    direction === 'left'
      ? 'WIRE HUM CONFIRMED. PATH REALIGNING...'
      : 'PHOSPHOR GLOW ACCEPTED. PATH REALIGNING...'
  );
  try {
    const response = await fetch('/api/progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        event: 'decision',
        direction,
        confidence: meta.confidence ?? null,
        via: meta.via ?? null,
      }),
    });
    if (!response.ok) {
      throw new Error('Decision failed');
    }
    const payload = await response.json();
    deactivateBranch();
    renderPayload(payload, { autoScroll: true });
  } catch (err) {
    setHudMessage('THE MAZE REFUSED THAT INPUT. TRY AGAIN.');
    branchResolving = false;
  } finally {
    branchResolving = false;
    pulseCurrentParagraph(false);
  }
}

function updateParagraphStates() {
  const scrollTop = storyWindow.scrollTop;
  const revealThreshold = 120;
  const blurThreshold = 60;
  const viewportCenter = scrollTop + storyWindow.clientHeight / 2;
  let closestState = null;
  let closestDelta = Number.POSITIVE_INFINITY;

  paragraphState.forEach((state) => {
    const { element } = state;
    const offsetTop = element.offsetTop;
    const bottom = offsetTop + element.offsetHeight;
    const elementCenter = offsetTop + element.offsetHeight / 2;
    const delta = Math.abs(elementCenter - viewportCenter);
    element.classList.remove('is-current');
    const wasPast = element.classList.contains('is-past');
    if (bottom < scrollTop - blurThreshold) {
      if (!wasPast) {
        element.classList.add('is-past');
        state.justMutated = false;
      }
    } else if (wasPast && bottom >= scrollTop + revealThreshold) {
      element.classList.remove('is-past');
      if (!state.justMutated) {
        mutateParagraph(state);
      }
    }
    if (delta < closestDelta) {
      closestDelta = delta;
      closestState = state;
    }
  });

  if (closestState) {
    closestState.element.classList.add('is-current');
    currentFocusedElement = closestState.element;
  }
}

async function mutateParagraph(state) {
  if (!sessionId || state.mutating) {
    return;
  }
  state.mutating = true;
  try {
    const response = await fetch('/api/paragraph/mutate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        paragraph_id: state.element.dataset.paragraphId,
      }),
    });
    if (!response.ok) {
      throw new Error('Mutation failed');
    }
    const payload = await response.json();
    if (payload.text) {
      state.element.textContent = payload.text;
      state.element.classList.add('is-mutated');
      setTimeout(() => state.element.classList.remove('is-mutated'), 1800);
      state.justMutated = true;
    }
    if (payload.hud_message) {
      setHudMessage(payload.hud_message);
    }
  } catch (err) {
    // ignore failures quietly to keep immersion
  } finally {
    state.mutating = false;
  }
}

function checkAutoAdvance() {
  if (storyComplete || autoAdvancePending || activeBranch || !sessionId) {
    return;
  }
  if (!isNearBottom()) {
    return;
  }
  autoAdvancePending = true;
  fetch('/api/progress', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      event: 'advance',
    }),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error('Advance failed');
      }
      return response.json();
    })
    .then((payload) => {
      renderPayload(payload, { autoScroll: true });
    })
    .catch(() => {
      setHudMessage('SIGNAL STUTTERED. TRY SCROLLING AGAIN.');
    })
    .finally(() => {
      autoAdvancePending = false;
    });
}

function isNearBottom() {
  const threshold = 220;
  return (
    storyWindow.scrollTop + storyWindow.clientHeight >
    storyContent.scrollHeight - threshold
  );
}

function scrollToBottom() {
  storyWindow.scrollTo({
    top: storyContent.scrollHeight,
    behavior: 'smooth',
  });
}

function setHudMessage(message) {
  hudMessageEl.textContent = message || '';
}

function handleStoryScroll() {
  pulseCurrentParagraph(false);
  updateParagraphStates();
  checkAutoAdvance();
}

function showRegistration() {
  if (!registerOverlay) {
    return;
  }
  if (!registrationAvailable) {
    setHudMessage('THE MAZE IS STILL WRITING. KEEP READING.');
    return;
  }
  registerOverlay.classList.remove('hidden');
  registrationShown = true;
  updateRegistrationUI();
  if (registerCloseBtn && typeof registerCloseBtn.focus === 'function') {
    registerCloseBtn.focus();
  }
}

function updateRegistrationUI() {
  if (!registerTriggerBtn) {
    return;
  }
  if (!registrationAvailable) {
    registerTriggerBtn.classList.add('hidden');
    registerTriggerBtn.disabled = false;
    registerTriggerBtn.textContent = 'Register';
    return;
  }
  registerTriggerBtn.classList.remove('hidden');
  if (profile?.name) {
    registerTriggerBtn.textContent = 'Registered';
    registerTriggerBtn.disabled = true;
  } else {
    registerTriggerBtn.textContent = 'Register';
    registerTriggerBtn.disabled = false;
  }
}

function pulseCurrentParagraph(active) {
  if (!currentFocusedElement) {
    return;
  }
  if (!active) {
    currentFocusedElement.classList.remove('is-tilted');
    return;
  }
  currentFocusedElement.classList.add('is-tilted');
  clearTimeout(tiltGlowTimeout);
  tiltGlowTimeout = setTimeout(() => {
    currentFocusedElement?.classList.remove('is-tilted');
  }, 600);
}

function prefillProfile() {
  if (profile?.name) {
    registerNameInput.value = profile.name;
  }
  if (profile?.email) {
    registerEmailInput.value = profile.email;
  }
  updateRegistrationUI();
}

function loadProfile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw);
  } catch (err) {
    return null;
  }
}
