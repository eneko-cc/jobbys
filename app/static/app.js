const $ = (sel) => document.querySelector(sel);
const deck = $("#deck");
const tpl = $("#card-tpl");
let current = null;
let busy = false;

const STATUS_LABELS = {
  pending: "En cours",
  sent: "Envoyée",
  dry_run: "Email prêt (test)",
  prefilled: "À valider dans le navigateur",
  to_do: "À envoyer toi-même",
  error: "Erreur",
};
const CHANNEL_LABELS = { email: "Email", form: "Formulaire", linkedin: "LinkedIn" };

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function safeUrl(url) {
  return /^https?:\/\//i.test(url || "") ? url : "#";
}

function fillList(list, items) {
  list.replaceChildren(...(items || []).map((item) => el("li", item)));
}

function renderCard(offer) {
  const a = offer.analysis;
  const card = tpl.content.firstElementChild.cloneNode(true);
  card.querySelector(".title").textContent = a.titre || offer.title;
  card.querySelector(".company").textContent = [a.entreprise || offer.company, a.lieu || offer.location]
    .filter(Boolean)
    .join(" · ");
  const score = card.querySelector(".score");
  score.querySelector("strong").textContent = `${a.score}%`;
  score.classList.add(a.score >= 70 ? "high" : a.score >= 45 ? "mid" : "low");

  const chips = [
    a.teletravail && `Télétravail : ${a.teletravail}`,
    a.contrat !== "Non précisé" && a.contrat,
    a.salaire !== "Non précisé" && a.salaire,
    a.experience !== "Non précisé" && a.experience,
  ].filter(Boolean);
  fillList(card.querySelector(".chips"), chips);
  card.querySelector(".resume").textContent = a.resume;
  card.querySelector(".why").textContent = a.raison_score;
  fillList(card.querySelector(".missions"), a.missions);
  fillList(card.querySelector(".profil"), a.profil_recherche);

  const sources = card.querySelector(".sources");
  sources.append("Vue sur : ");
  offer.sources.forEach((s, i) => {
    if (i) sources.append(", ");
    const link = el("a", s.source);
    link.href = safeUrl(s.url);
    link.target = "_blank";
    link.rel = "noopener";
    sources.append(link);
  });

  enableDrag(card);
  return card;
}

function renderEmpty(text) {
  deck.replaceChildren(el("div", text, "empty"));
}

async function loadNext() {
  const { offer } = await api("/api/offers/next");
  current = offer;
  if (!offer) {
    const { counts, fetch: f } = await api("/api/status");
    if (f.running || counts.analyzing) {
      renderEmpty("Analyse des offres en cours…");
    } else {
      renderEmpty("Plus d'offres à trier. Clique sur « Chercher des offres » pour en récupérer.");
    }
    return;
  }
  deck.replaceChildren(renderCard(offer));
}

async function swipe(direction) {
  if (!current || busy) return;
  busy = true;
  const card = deck.querySelector(".card");
  const offer = current;
  if (card) {
    card.style.transform = `translateX(${direction === "like" ? 140 : -140}%) rotate(${direction === "like" ? 18 : -18}deg)`;
    card.style.opacity = "0";
  }
  try {
    await api(`/api/offers/${offer.id}/swipe`, {
      method: "POST",
      body: JSON.stringify({ direction }),
    });
    if (direction === "like") {
      showBanner(`Candidature lancée pour « ${offer.analysis.titre || offer.title} ». Suivi dans l'onglet Candidatures.`);
    }
  } catch (err) {
    showBanner(`Erreur : ${err.message}`);
  }
  setTimeout(async () => {
    busy = false;
    await loadNext();
    refreshStatus();
  }, 250);
}

function enableDrag(card) {
  let startX = 0;
  let dx = 0;
  let dragging = false;
  const like = card.querySelector(".stamp-like");
  const nope = card.querySelector(".stamp-nope");

  card.addEventListener("pointerdown", (e) => {
    if (e.target.closest("a")) return;
    dragging = true;
    startX = e.clientX;
    dx = 0;
    card.classList.add("dragging");
    card.setPointerCapture(e.pointerId);
  });
  card.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    dx = e.clientX - startX;
    card.style.transform = `translateX(${dx}px) rotate(${dx / 18}deg)`;
    like.style.opacity = Math.max(0, Math.min(1, dx / 100));
    nope.style.opacity = Math.max(0, Math.min(1, -dx / 100));
  });
  const end = () => {
    if (!dragging) return;
    dragging = false;
    card.classList.remove("dragging");
    if (dx > 110) return swipe("like");
    if (dx < -110) return swipe("pass");
    card.style.transform = "";
    like.style.opacity = nope.style.opacity = 0;
  };
  card.addEventListener("pointerup", end);
  card.addEventListener("pointercancel", end);
}

function showBanner(text) {
  const banner = $("#banner");
  banner.textContent = text;
  banner.hidden = false;
  clearTimeout(showBanner.timer);
  showBanner.timer = setTimeout(() => (banner.hidden = true), 6000);
}

async function refreshStatus() {
  const { counts, fetch: f, profile_ready, claude_ready, email_dry_run } = await api("/api/status");
  const parts = [`${counts.ready} à trier`];
  if (counts.analyzing) parts.push(`${counts.analyzing} en analyse`);
  parts.push(`${counts.liked} likées`);
  if (email_dry_run) parts.push("emails en mode test");
  $("#counts").textContent = parts.join(" · ");
  const button = $("#fetch");
  button.disabled = f.running;
  button.textContent = f.running ? "Recherche…" : "Chercher des offres";
  if ((!profile_ready || !claude_ready) && !refreshStatus.warned) {
    refreshStatus.warned = true;
    showView("settings");
    showBanner("Bienvenue ! Remplis tes réglages (au moins la clé Claude, une source et les postes recherchés), puis enregistre.");
  }
  if (f.errors.length && !f.running && refreshStatus.lastErrors !== f.errors.join()) {
    refreshStatus.lastErrors = f.errors.join();
    showBanner(f.errors.join(" | "));
  }
  if (!current && !busy) loadNext();
  return { counts, f };
}

async function loadApps() {
  const { applications } = await api("/api/applications");
  const list = $("#apps");
  if (!applications.length) {
    list.replaceChildren(el("li", "Aucune candidature pour l'instant. Like une offre pour commencer."));
    return;
  }
  list.replaceChildren(
    ...applications.map((app) => {
      const li = el("li");
      const head = el("div", null, "app-head");
      const title = el("strong", `${app.title} · ${app.company || ""}`);
      const badge = el("span", `${CHANNEL_LABELS[app.channel] || app.channel} · ${STATUS_LABELS[app.status] || app.status}`, `badge ${app.status}`);
      head.append(title, badge);
      li.append(head);
      if (app.detail) li.append(el("p", app.detail, "detail"));
      const link = el("a", "Voir l'offre");
      link.href = safeUrl(app.apply_url || app.url);
      link.target = "_blank";
      link.rel = "noopener";
      li.append(link);
      if (app.message) {
        const details = el("details");
        details.append(el("summary", "Message envoyé / à coller"), el("pre", app.message));
        const copy = el("button", "Copier le message", "copy");
        copy.onclick = async () => {
          await navigator.clipboard.writeText(app.message);
          copy.textContent = "Copié";
        };
        details.append(copy);
        li.append(details);
      }
      return li;
    }),
  );
}

function showView(view) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  for (const name of ["swipe", "apps", "settings"]) $(`#view-${name}`).hidden = name !== view;
  if (view === "apps") loadApps();
  if (view === "settings") loadSettings();
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => showView(tab.dataset.view)));

async function loadSettings() {
  const { settings, profile, cv_ready } = await api("/api/settings");
  document.querySelectorAll("[data-profile]").forEach((input) => {
    const value = profile[input.dataset.profile];
    input.value = input.hasAttribute("data-list") ? (value || []).join("\n") : value ?? "";
  });
  document.querySelectorAll("[data-setting]").forEach((input) => {
    const value = settings[input.dataset.setting];
    if (input.type === "checkbox") input.checked = Boolean(value);
    else if (input.type === "password") {
      input.value = "";
      input.placeholder = value ? "Enregistrée" : "";
    } else input.value = value ?? "";
  });
  $("#cv-status").textContent = cv_ready ? "CV enregistré. Choisis un fichier pour le remplacer." : "Aucun CV pour l'instant.";
}

$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const profile = {};
  document.querySelectorAll("[data-profile]").forEach((input) => {
    profile[input.dataset.profile] = input.hasAttribute("data-list")
      ? input.value.split("\n").map((v) => v.trim()).filter(Boolean)
      : input.value.trim();
  });
  const settings = {};
  document.querySelectorAll("[data-setting]").forEach((input) => {
    settings[input.dataset.setting] = input.type === "checkbox" ? input.checked : input.value.trim();
  });
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ settings, profile }) });
    await loadSettings();
    showBanner("Réglages enregistrés.");
    refreshStatus();
  } catch (err) {
    showBanner(`Erreur : ${err.message}`);
  }
});

$("#cv").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/cv", { method: "POST", body: form });
  showBanner(res.ok ? "CV enregistré." : `Erreur : ${(await res.json()).detail}`);
  e.target.value = "";
  loadSettings();
});

$("#fetch").addEventListener("click", async () => {
  await api("/api/fetch", { method: "POST" });
  showBanner("Recherche lancée sur toutes les sources configurées…");
  refreshStatus();
});
$("#like").addEventListener("click", () => swipe("like"));
$("#pass").addEventListener("click", () => swipe("pass"));
document.addEventListener("keydown", (e) => {
  if (!$("#view-swipe").hidden && e.key === "ArrowRight") swipe("like");
  if (!$("#view-swipe").hidden && e.key === "ArrowLeft") swipe("pass");
});

setInterval(() => {
  refreshStatus();
  if (!$("#view-apps").hidden) loadApps();
}, 4000);
refreshStatus();
loadNext();
