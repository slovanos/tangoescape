// Keeps event lists honest between builds: anything that has ended is hidden
// from "upcoming" lists, and a past event's page stops offering registration.
(() => {
  const now = Date.now();
  const isOver = (el) => {
    const end = Date.parse(el.dataset.eventEnd);
    return !Number.isNaN(end) && end < now;
  };

  const lists = [...document.querySelectorAll('[data-upcoming]')];
  lists.forEach((list) => {
    const rows = [...list.querySelectorAll('[data-event-end]')];
    rows.forEach((row) => { if (isOver(row)) row.hidden = true; });

    const visible = rows.filter((row) => !row.hidden);
    if (list.hasAttribute('data-feature-first')) {
      rows.forEach((row) => row.classList.remove('is-next'));
      if (visible[0]) visible[0].classList.add('is-next');
    }
    if (visible.length === 0) {
      list.hidden = true;
      const group = list.closest('[data-group]');
      if (group) group.hidden = true;
    }
  });

  // An empty note shows only once every list that points at it is empty
  new Set(lists.map((list) => list.dataset.emptyTarget)).forEach((id) => {
    const empty = document.getElementById(id);
    if (empty && lists.every((list) => list.dataset.emptyTarget !== id || list.hidden)) empty.hidden = false;
  });

  const page = document.querySelector('[data-event-page]');
  if (page && isOver(page)) {
    page.classList.add('is-past');
    page.querySelectorAll('[data-when-past]').forEach((el) => { el.hidden = false; });
    page.querySelectorAll('[data-hide-when-past]').forEach((el) => { el.hidden = true; });
  }
})();
