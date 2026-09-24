'use strict';
document.querySelectorAll('[data-local-time]').forEach(el => {
  const date = new Date(el.dateTime);
  if (!Number.isNaN(date.getTime())) {
    el.textContent = new Intl.DateTimeFormat(undefined, {dateStyle:'medium',timeStyle:'short'}).format(date);
    el.title = el.dateTime + ' (UTC)';
  }
});
const panel = document.getElementById('chat-panel');
const toggle = document.getElementById('chat-toggle');
function closeChat() {
  if (!panel) return;
  panel.hidden = true;
  toggle.setAttribute('aria-expanded', 'false');
  toggle.focus();
}
if (toggle) {
  toggle.addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute('aria-expanded', String(!panel.hidden));
    if (!panel.hidden) document.getElementById('chat-question').focus();
  });
  document.getElementById('chat-close').addEventListener('click', closeChat);
  document.addEventListener('keydown', e => {if (e.key === 'Escape' && !panel.hidden) closeChat();});
  document.getElementById('chat-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget;
    const button = form.querySelector('button');
    const answer = document.getElementById('chat-answer');
    button.disabled = true;
    answer.textContent = 'Looking at the numbers…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(form.action, {method:'POST', signal:controller.signal,
        headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content},
        body:JSON.stringify({message:document.getElementById('chat-question').value,
                             team_id:Number(document.getElementById('chat-team').value)})});
      const data = await response.json();
      answer.textContent = response.ok ? data.answer : (data.error || 'The request could not be completed.');
    } catch (_) {answer.textContent = 'Could not reach the analyst. Please try again.';}
    finally {clearTimeout(timeout); button.disabled = false;}
  });
}
document.querySelectorAll('.favorite-button').forEach(button => {
  try {
    const saved = JSON.parse(localStorage.getItem('pl-favourite') || 'null');
    if (saved && saved.id === button.dataset.teamId) button.textContent = 'Favourite saved ✓';
    button.addEventListener('click', () => {
      localStorage.setItem('pl-favourite', JSON.stringify({id:button.dataset.teamId,name:button.dataset.teamName}));
      button.textContent = 'Favourite saved ✓';
    });
  } catch (_) {button.hidden = true;}
});

const favouriteShortcut = document.getElementById('favorite-shortcut');
if (favouriteShortcut) {
  try {
    const saved = JSON.parse(localStorage.getItem('pl-favourite') || 'null');
    const club = saved && Array.from(document.querySelectorAll('#chat-team option')).find(option => option.value === saved.id);
    if (club) {
      favouriteShortcut.textContent = 'Favourite: ' + club.textContent;
      favouriteShortcut.href = '/team/' + encodeURIComponent(club.value) + '?season=' + encodeURIComponent(favouriteShortcut.dataset.season);
      favouriteShortcut.hidden = false;
    }
  } catch (_) { /* Storage is optional. */ }
}

// Images enhance identity; readable names and initials survive unavailable photos.
document.querySelectorAll('[data-image-fallback]').forEach(img => {
  const fallback = () => {
    img.hidden = true;
    const placeholder = img.nextElementSibling;
    if (placeholder) placeholder.hidden = false;
  };
  img.addEventListener('error', fallback);
  if (img.complete && img.naturalWidth === 0) fallback();
});
const swapClubs = document.getElementById('swap-clubs');
if (swapClubs) swapClubs.addEventListener('click', () => {
  const form = swapClubs.closest('form');
  const left = form.elements.left, right = form.elements.right;
  [left.value, right.value] = [right.value, left.value];
  form.requestSubmit();
});
document.querySelectorAll('[data-table-search]').forEach(input => {
  input.addEventListener('input', () => {
    const table = document.getElementById(input.dataset.tableSearch);
    const query = input.value.trim().toLocaleLowerCase();
    const rows = Array.from(table.querySelectorAll('[data-search-row]'));
    rows.forEach(row => {row.hidden = !row.textContent.toLocaleLowerCase().includes(query);});
    const empty = table.closest('.panel').querySelector('.search-empty');
    if (empty) empty.hidden = !rows.length || rows.some(row => !row.hidden);
  });
});
const scenario = document.getElementById('scenario-form');
if (scenario) {
  const update = () => {
    const rows = Array.from(scenario.querySelectorAll('.scenario-row'));
    const count = rows.filter(row => Array.from(row.querySelectorAll('input')).every(i => i.value !== '' && i.checkValidity())).length;
    document.getElementById('scenario-count').textContent = `${count} of ${rows.length} matches set · calculate to see the table`;
  };
  scenario.addEventListener('input', update);
  update();
}
const squadSearch = document.getElementById('squad-search');
const squadPosition = document.getElementById('squad-position');
if (squadSearch && squadPosition) {
  const normalizeName = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  const filterSquad = () => {
    const query = normalizeName(squadSearch.value.trim());
    const cards = Array.from(document.querySelectorAll('[data-squad-player]'));
    cards.forEach(card => {
      card.hidden = !normalizeName(card.dataset.playerName).includes(query) || Boolean(squadPosition.value && card.dataset.position !== squadPosition.value);
    });
    const count = cards.filter(card => !card.hidden).length;
    document.getElementById('squad-count').textContent = `${count} of ${cards.length} players`;
    document.getElementById('squad-empty').hidden = count !== 0;
  };
  squadSearch.addEventListener('input', filterSquad);
  squadPosition.addEventListener('change', filterSquad);
}
