// 2026-11-25 - smart-voca - 단축키, 시험 자동 넘김(0.3초), 확인 대화상자
// 파일 위치: src/smartvoca/web/static/app.js
//
// JS 는 "누르는 방법"만 늘린다. 무엇이 켜지고 꺼지는지는 서버가 HTML 에 이미 적어 보냈다.
//   data-key="ArrowRight Enter"  : 이 키를 누르면 이 버튼을 누른 것과 같다 (꺼진 버튼은 건너뜀)
//   data-auto-advance            : 보기를 고르면 0.3초 뒤 폼을 보낸다 (UD-05)
//   data-confirm="..."           : 폼을 보내기 전에 확인 대화상자를 띄운다 (DL-03)
//   data-autosubmit              : 안의 입력이 바뀌면 바로 폼을 보낸다 (체크 상자, 파일 고르기)
//   data-reveal                  : 가린 뜻을 연다 (UD-04)
//   data-speak="word"            : 누르면 그 단어를 읽어 준다 (ADR-24)
//   data-theme-choice="dark"     : 밝기를 고른다 — 자동·밝게·어둡게 (ADR-23)
//   data-accent-choice="sea"     : 강조색을 고른다 (ADR-32)
"use strict";

const AUTO_ADVANCE_MS = 300; // 고른 보기를 눈으로 확인할 틈 (UD-05)

// ── 단축키 ────────────────────────────────────────────────
function keyName(event) {
  if (event.key === " ") return "Space";
  // 글자 키는 자판 위치(code)로 판정한다. 한글 입력 상태에서는 key 가 "ㅔ" 처럼 들어와 "p" 와 맞지 않는다
  if (/^Key[A-Z]$/.test(event.code)) return event.code.slice(3).toLowerCase();
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
  if (event.target.closest("[data-theme-menu]")) return; // 테마 메뉴 안의 키는 메뉴가 쓴다 (Enter 로 시험이 시작되지 않게)

  // Ctrl+F: 단어 목록 화면에서는 브라우저 찾기 대신 검색창으로 간다
  const search = document.querySelector("[data-search]");
  if (event.ctrlKey && keyName(event) === "f" && search) {
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

// ── 테마: 밝기(ADR-23) × 강조색(ADR-32) ──────────────────
// 선택은 이 브라우저에만 기억한다(localStorage). 학습 기록이 아니라 보기 설정이고,
// 로그인이 없어 DB 에 두면 서버에 들어온 모든 사람의 화면이 함께 바뀌기 때문이다.
// 처음 그릴 때의 적용은 base.html <head> 의 짧은 스크립트가 한다(화면이 번쩍이지 않게). 여기서는 바꾸기만 한다.
const DEFAULTS = { theme: "auto", accent: "indigo" };

function remember(key, value, defaultValue) {
  try {
    if (value === defaultValue) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch (error) {
    // 저장을 못 해도 지금 화면에는 적용된다
  }
}

function setRootData(name, value, defaultValue) {
  if (value === defaultValue) delete document.documentElement.dataset[name];
  else document.documentElement.dataset[name] = value;
}

// 지금 고른 칩에 aria-pressed 를 켠다 (모양은 CSS 가 [aria-pressed="true"] 로 그린다)
function markThemeChoices() {
  const theme = document.documentElement.dataset.theme || DEFAULTS.theme;
  const accent = document.documentElement.dataset.accent || DEFAULTS.accent;
  for (const chip of document.querySelectorAll("[data-theme-choice]")) {
    chip.setAttribute("aria-pressed", String(chip.dataset.themeChoice === theme));
  }
  for (const chip of document.querySelectorAll("[data-accent-choice]")) {
    chip.setAttribute("aria-pressed", String(chip.dataset.accentChoice === accent));
  }
}

document.addEventListener("click", (event) => {
  const themeChip = event.target.closest("[data-theme-choice]");
  const accentChip = event.target.closest("[data-accent-choice]");
  if (themeChip) {
    setRootData("theme", themeChip.dataset.themeChoice, DEFAULTS.theme);
    remember("smartvoca-theme", themeChip.dataset.themeChoice, DEFAULTS.theme);
  } else if (accentChip) {
    setRootData("accent", accentChip.dataset.accentChoice, DEFAULTS.accent);
    remember("smartvoca-accent", accentChip.dataset.accentChoice, DEFAULTS.accent);
  } else {
    // 메뉴 바깥을 누르면 닫는다
    for (const menu of document.querySelectorAll("[data-theme-menu][open]")) {
      if (!menu.contains(event.target)) menu.open = false;
    }
    return;
  }
  markThemeChoices();
});

for (const menu of document.querySelectorAll("[data-theme-menu]")) {
  // 메뉴가 열려 있을 때 Esc 는 메뉴만 닫는다 (화면의 '뒤로' 단축키로 넘기지 않는다)
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.open) {
      event.stopPropagation();
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
}
markThemeChoices();

// ── 발음 듣기 (ADR-24) ─────────────────────────────────────
// 브라우저에 내장된 음성 합성을 쓴다. 내 PC 에 설치된 영어 음성(localService)을 먼저 골라 인터넷 없이 읽는다.
function pickEnglishVoice() {
  const english = window.speechSynthesis.getVoices().filter((voice) => /^en([-_]|$)/i.test(voice.lang));
  return (
    english.find((voice) => voice.localService && /en[-_]US/i.test(voice.lang)) ||
    english.find((voice) => voice.localService) ||
    english[0] ||
    null
  );
}

function speak(text, button) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel(); // 읽던 것이 있으면 멈추고 새로 읽는다
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.9;
  const voice = pickEnglishVoice();
  if (voice) utterance.voice = voice;
  if (button) {
    button.classList.add("is-speaking");
    utterance.onend = utterance.onerror = () => button.classList.remove("is-speaking");
  }
  window.speechSynthesis.speak(utterance);
}

if ("speechSynthesis" in window) {
  window.speechSynthesis.getVoices(); // 음성 목록은 처음 부를 때 늦게 채워지므로 미리 한 번 부른다
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-speak]");
  if (!button) return;
  event.preventDefault();
  speak(button.dataset.speak, button);
});
