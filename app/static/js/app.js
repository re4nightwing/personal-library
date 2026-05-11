/* Home Library — main app JS */
'use strict';

const COLOR_PALETTE = [
  '#ef4444','#f97316','#eab308','#22c55e',
  '#06b6d4','#3b82f6','#8b5cf6','#ec4899',
  '#14b8a6','#f43f5e','#84cc16','#6366f1',
];

// ── State ────────────────────────────────────────────────────────────────────
let allTags = window.__TAGS__ || [];
let books = [];
let searchTimer = null;
let activeTagFilter = null;
let editingBookId = null;
let editingTagId = null;
let selectedTagIds = new Set();
let currentQuery = '';

// ── DOM refs ─────────────────────────────────────────────────────────────────
const booksGrid        = document.getElementById('booksGrid');
const searchInput      = document.getElementById('searchInput');
const searchHint       = document.getElementById('searchHint');
const bookModal        = document.getElementById('bookModal');
const bookTitleInput   = document.getElementById('bookTitleInput');
const tagSelector      = document.getElementById('tagSelector');
const tagModal         = document.getElementById('tagModal');
const tagNameInput     = document.getElementById('tagNameInput');
const tagColorInput    = document.getElementById('tagColorInput');
const colorSwatches    = document.getElementById('colorSwatches');
const tagFilterList    = document.getElementById('tagFilterList');
const tagManagerList   = document.getElementById('tagManagerList');
const newTagInlineInput = document.getElementById('newTagInlineInput');
const newTagColorPicker = document.getElementById('newTagColorPicker');
const modalTitle       = document.getElementById('modalTitle');
const tagModalTitle    = document.getElementById('tagModalTitle');

// ── Utility ───────────────────────────────────────────────────────────────────
const api = {
  async get(url) {
    const r = await fetch(url, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(url, data) {
    const r = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async put(url, data) {
    const r = await fetch(url, {
      method: 'PUT', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async del(url) {
    const r = await fetch(url, { method: 'DELETE', credentials: 'same-origin' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { year:'numeric', month:'short', day:'numeric' });
}

// ── Search ────────────────────────────────────────────────────────────────────
async function doSearch(q = '', tagId = null) {
  currentQuery = q;
  let url = `/api/search?q=${encodeURIComponent(q)}`;
  if (tagId) url += `&tag_id=${tagId}`;
  books = await api.get(url);
  renderBooks();
}

searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  searchHint.textContent = q ? '' : '';
  searchTimer = setTimeout(() => doSearch(q, activeTagFilter), 150);
});

// ── Books rendering ───────────────────────────────────────────────────────────
function renderBooks() {
  if (!books.length) {
    booksGrid.innerHTML = `
      <div class="empty-state">
        <h3>${currentQuery ? 'No books found' : 'Your library is empty'}</h3>
        <p>${currentQuery ? 'Try a different search term.' : 'Add your first book with the button above.'}</p>
      </div>`;
    return;
  }
  booksGrid.innerHTML = books.map(b => bookCardHTML(b)).join('');
}

function bookCardHTML(b) {
  const tagsHtml = (b.tags || []).map(t =>
    `<span class="book-tag" style="background:${escHtml(t.color)}">${escHtml(t.name)}</span>`
  ).join('');
  return `
    <div class="book-card" data-id="${b.id}">
      <div class="book-top">
        <div class="book-title">${escHtml(b.title)}</div>
        <div class="book-actions">
          <button class="btn-icon" onclick="openEditBook(${b.id})" title="Edit">✎</button>
          <button class="btn-icon danger" onclick="removeBook(${b.id})" title="Delete" style="color:var(--text-muted)">✕</button>
        </div>
      </div>
      ${tagsHtml ? `<div class="book-tags">${tagsHtml}</div>` : ''}
      <div class="book-meta">Added ${formatDate(b.created_at)}</div>
    </div>`;
}

// ── Tag filter sidebar ────────────────────────────────────────────────────────
function renderTagFilters() {
  // keep "All books" button, rebuild the rest
  const existing = tagFilterList.querySelectorAll('[data-tag-id]:not([data-tag-id=""])');
  existing.forEach(el => el.remove());
  allTags.forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'tag-filter' + (activeTagFilter == t.id ? ' active' : '');
    btn.dataset.tagId = t.id;
    btn.style.setProperty('--tc', t.color);
    btn.textContent = t.name;
    tagFilterList.appendChild(btn);
  });
}

tagFilterList.addEventListener('click', e => {
  const btn = e.target.closest('.tag-filter');
  if (!btn) return;
  tagFilterList.querySelectorAll('.tag-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tagId = btn.dataset.tagId || null;
  activeTagFilter = tagId ? parseInt(tagId) : null;
  doSearch(searchInput.value.trim(), activeTagFilter);
});

function renderTagManager() {
  tagManagerList.innerHTML = allTags.map(t => `
    <div class="tag-manager-row" data-tag-id="${t.id}">
      <span class="tag-chip" style="background:${escHtml(t.color)}">${escHtml(t.name)}</span>
      <button class="btn-icon-sm" onclick="editTag(${t.id}, '${escHtml(t.name)}', '${escHtml(t.color)}')">✎</button>
      <button class="btn-icon-sm danger" onclick="deleteTag(${t.id})">✕</button>
    </div>`).join('');
}

// ── Book modal ────────────────────────────────────────────────────────────────
function renderTagSelector() {
  tagSelector.innerHTML = allTags.map(t => `
    <button
      class="tag-option${selectedTagIds.has(t.id) ? ' selected' : ''}"
      style="background:${escHtml(t.color)}"
      data-tag-id="${t.id}"
      onclick="toggleTagSelection(${t.id}, this)"
    >${escHtml(t.name)}</button>`).join('');
}

function toggleTagSelection(tagId, el) {
  if (selectedTagIds.has(tagId)) {
    selectedTagIds.delete(tagId);
    el.classList.remove('selected');
  } else {
    selectedTagIds.add(tagId);
    el.classList.add('selected');
  }
}

function openAddBook() {
  editingBookId = null;
  selectedTagIds.clear();
  bookTitleInput.value = '';
  modalTitle.textContent = 'Add Book';
  renderTagSelector();
  bookModal.hidden = false;
  bookTitleInput.focus();
}

function openEditBook(id) {
  const book = books.find(b => b.id === id);
  if (!book) return;
  editingBookId = id;
  selectedTagIds = new Set((book.tags || []).map(t => t.id));
  bookTitleInput.value = book.title;
  modalTitle.textContent = 'Edit Book';
  renderTagSelector();
  bookModal.hidden = false;
  bookTitleInput.focus();
}

async function saveBook() {
  const title = bookTitleInput.value.trim();
  if (!title) { bookTitleInput.focus(); return; }
  const tag_ids = [...selectedTagIds];
  try {
    if (editingBookId) {
      const updated = await api.put(`/api/books/${editingBookId}`, { title, tag_ids });
      const idx = books.findIndex(b => b.id === editingBookId);
      if (idx >= 0) books[idx] = updated;
    } else {
      const newBook = await api.post('/api/books', { title, tag_ids });
      books.unshift(newBook);
    }
    renderBooks();
    bookModal.hidden = true;
  } catch(e) {
    alert('Error saving book: ' + e.message);
  }
}

async function removeBook(id) {
  if (!confirm('Delete this book?')) return;
  await api.del(`/api/books/${id}`);
  books = books.filter(b => b.id !== id);
  renderBooks();
}

// Inline tag creation inside book modal
document.getElementById('btnCreateTagInline').addEventListener('click', async () => {
  const name = newTagInlineInput.value.trim();
  if (!name) return;
  try {
    const tag = await api.post('/api/tags', { name, color: newTagColorPicker.value });
    allTags.push(tag);
    allTags.sort((a,b) => a.name.localeCompare(b.name));
    selectedTagIds.add(tag.id);
    newTagInlineInput.value = '';
    renderTagSelector();
    renderTagFilters();
    renderTagManager();
  } catch(e) {
    alert('Could not create tag: ' + e.message);
  }
});

// ── Tag modal ─────────────────────────────────────────────────────────────────
function buildColorSwatches(selected) {
  colorSwatches.innerHTML = COLOR_PALETTE.map(c =>
    `<div class="color-swatch${c===selected?' selected':''}" style="background:${c}" data-color="${c}" onclick="selectSwatch(this, '${c}')"></div>`
  ).join('');
}

window.selectSwatch = function(el, color) {
  colorSwatches.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
  el.classList.add('selected');
  tagColorInput.value = color;
};

document.getElementById('btnNewTag').addEventListener('click', () => {
  editingTagId = null;
  tagNameInput.value = '';
  tagColorInput.value = '#6366f1';
  tagModalTitle.textContent = 'New Tag';
  buildColorSwatches('#6366f1');
  tagModal.hidden = false;
  tagNameInput.focus();
});

window.editTag = function(id, name, color) {
  editingTagId = id;
  tagNameInput.value = name;
  tagColorInput.value = color;
  tagModalTitle.textContent = 'Edit Tag';
  buildColorSwatches(color);
  tagModal.hidden = false;
  tagNameInput.focus();
};

tagColorInput.addEventListener('input', () => {
  colorSwatches.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
});

async function saveTag() {
  const name = tagNameInput.value.trim();
  if (!name) { tagNameInput.focus(); return; }
  const color = tagColorInput.value;
  try {
    if (editingTagId) {
      const updated = await api.put(`/api/tags/${editingTagId}`, { name, color });
      const idx = allTags.findIndex(t => t.id === editingTagId);
      if (idx >= 0) allTags[idx] = updated;
    } else {
      const tag = await api.post('/api/tags', { name, color });
      allTags.push(tag);
    }
    allTags.sort((a,b) => a.name.localeCompare(b.name));
    renderTagFilters();
    renderTagManager();
    tagModal.hidden = true;
    doSearch(searchInput.value.trim(), activeTagFilter);
  } catch(e) {
    alert('Error saving tag: ' + e.message);
  }
}

window.deleteTag = async function(id) {
  if (!confirm('Delete this tag? It will be removed from all books.')) return;
  await api.del(`/api/tags/${id}`);
  allTags = allTags.filter(t => t.id !== id);
  if (activeTagFilter === id) { activeTagFilter = null; }
  renderTagFilters();
  renderTagManager();
  doSearch(searchInput.value.trim(), activeTagFilter);
};

// ── Wire up buttons & close handlers ─────────────────────────────────────────
document.getElementById('btnAddBook').addEventListener('click', openAddBook);
document.getElementById('btnModalSave').addEventListener('click', saveBook);
document.getElementById('btnModalClose').addEventListener('click', () => bookModal.hidden = true);
document.getElementById('btnModalCancel').addEventListener('click', () => bookModal.hidden = true);
document.getElementById('btnTagSave').addEventListener('click', saveTag);
document.getElementById('btnTagModalClose').addEventListener('click', () => tagModal.hidden = true);
document.getElementById('btnTagCancel').addEventListener('click', () => tagModal.hidden = true);

// Close on overlay click
bookModal.addEventListener('click', e => { if (e.target === bookModal) bookModal.hidden = true; });
tagModal.addEventListener('click', e => { if (e.target === tagModal) tagModal.hidden = true; });

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { bookModal.hidden = true; tagModal.hidden = true; }
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); searchInput.focus(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'n' && bookModal.hidden) { e.preventDefault(); openAddBook(); }
  if (e.key === 'Enter' && !bookModal.hidden) { e.preventDefault(); saveBook(); }
  if (e.key === 'Enter' && !tagModal.hidden) { e.preventDefault(); saveTag(); }
});

// ── Init ──────────────────────────────────────────────────────────────────────
doSearch('', null);
