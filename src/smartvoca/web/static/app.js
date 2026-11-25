// 2026-11-25 - smart-voca - 단축키, 시험 자동 넘김(0.3초), 확인 대화상자
// 파일 위치: src/smartvoca/web/static/app.js
//
// JS 는 "누르는 방법"만 늘린다. 무엇이 켜지고 꺼지는지는 서버가 HTML 에 이미 적어 보냈다.
//   data-key="ArrowRight Enter"  : 이 키를 누르면 이 버튼을 누른 것과 같다 (꺼진 버튼은 건너뜀)
//   data-auto-advance            : 보기를 고르면 0.3초 뒤 폼을 보낸다 (UD-05)
//   data-confirm="..."           : 폼을 보내기 전에 확인 대화상자를 띄운다 (DL-03)
//   data-autosubmit              : 안의 입력이 바뀌면 바로 폼을 보낸다 (체크 상자, 파일 고르기)
//   data-reveal                  : 가린 뜻을 연다 (UD-04)
"use strict";

const AUTO_ADVANCE_MS = 300; // 고른 보기를 눈으로 확인할 틈 (UD-05)

// ── 단축키 ────────────────────────────────────────────────
function keyName(event) {
  if (event.key === " ") return "Space";
  return event.key;
}

function findKeyTarget(name) {
  for (const element of document.querySelectorAll("[data-key]")) {
    const keys = element.dataset.key.split(" ");
    if (keys.includes(name) && !element.disabled) return element;
  }
  return null;
}

document.addEventListener("keydown", (event) => {
  if (event.altKey || event.metaKey) return;
  if (document.querySelector("dialog[open]")) return; // 대화상자가 떠 있으면 대화상자가 키를 받는다

  // Ctrl+F: 단어 목록 화면에서는 브라우저 찾기 대신 검색창으로 간다
  const search = document.querySelector("[data-search]");
  if (event.ctrlKey && event.key.toLowerCase() === "f" && search) {
    event.preventDefault();
    search.focus();
    search.select();
    return;
  }
  if (event.ctrlKey) return;

  const name = keyName(event);
  const active = document.activeElement;
  const typing = active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA");
  if (typing && name !== "Escape") return; // 글자를 치는 중에는 Esc 만 가로챈다
  // 초점이 이미 버튼·링크에 있으면 Enter·Space 는 브라우저가 그 버튼을 누르게 둔다
  const onControl = active && active.matches("button, a, input, label");
  if (onControl && (name === "Enter" || name === "Space")) return;

  const target = findKeyTarget(name);
  if (target) {
    event.preventDefault();
    target.click();
  }
});

// ── 시험 자동 넘김 (UD-05) ─────────────────────────────────
// 보기를 누르면 바로 보내지 않고 선택 표시만 바꾼 뒤 0.3초 기다린다.
// 그 사이 다른 보기를 누르면 다시 기다린다. 다른 버튼(이전·다음·번호 점)을 누르면 페이지가 바뀌어 저절로 취소된다.
for (const form of document.querySelectorAll("form[data-auto-advance]")) {
  let timer = null;
  const choiceInput = document.createElement("input");
  choiceInput.type = "hidden";
  choiceInput.name = "choice";
  form.append(choiceInput);

  for (const button of form.querySelectorAll("button[name=choice]")) {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      for (const other of form.querySelectorAll("button[name=choice]")) {
        const selected = other === button;
        other.classList.toggle("is-selected", selected);
        other.setAttribute("aria-pressed", selected ? "true" : "false");
      }
      choiceInput.value = button.value;
      clearTimeout(timer);
      timer = setTimeout(() => form.submit(), AUTO_ADVANCE_MS);
    });
  }
}

// ── 확인 대화상자 (DL-03) ──────────────────────────────────
const dialog = document.getElementById("confirm-dialog");

for (const form of document.querySelectorAll("form[data-confirm]")) {
  form.addEventListener("submit", (event) => {
    if (!dialog || typeof dialog.showModal !== "function") {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
      return;
    }
    event.preventDefault();
    dialog.querySelector(".dialog-title").textContent = form.dataset.confirmTitle || "확인";
    dialog.querySelector(".dialog-text").textContent = form.dataset.confirm;
    dialog.querySelector("[data-role=yes]").textContent = form.dataset.confirmYes || "예";
    dialog.querySelector("[data-role=no]").textContent = form.dataset.confirmNo || "아니오";
    dialog.onclose = () => {
      if (dialog.returnValue === "yes") form.submit(); // form.submit() 은 submit 이벤트를 다시 부르지 않는다
    };
    dialog.returnValue = "";
    dialog.showModal();
    dialog.querySelector("[data-role=no]").focus(); // 안전한 쪽에 초점
  });
}

// ── 바뀌면 바로 보내기 ─────────────────────────────────────
for (const form of document.querySelectorAll("form[data-autosubmit]")) {
  form.addEventListener("change", () => form.submit());
}

// ── 가린 뜻 열기 (UD-04) ───────────────────────────────────
for (const button of document.querySelectorAll("[data-reveal]")) {
  button.addEventListener("click", () => {
    const meaning = document.querySelector("[data-testid=meaning]");
    if (meaning) meaning.hidden = false;
    button.remove(); // 이미 열었으니 Space 는 더 할 일이 없다
  });
}
