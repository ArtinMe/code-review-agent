function renderComment(container, comment) {
  const item = document.createElement("li");
  item.innerHTML = `<b>${comment.author}</b>: ${comment.body}`;
  container.appendChild(item);
}

export function renderAll(container, comments) {
  container.replaceChildren();
  comments.forEach((c) => renderComment(container, c));
}
