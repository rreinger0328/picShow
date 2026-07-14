const searchInput = document.querySelector("#gallery-search");
const filterButtons = Array.from(document.querySelectorAll("[data-filter]"));
const tiles = Array.from(document.querySelectorAll(".tile"));
const emptyResult = document.querySelector("#empty-result");

let activeFilter = "all";
let activeSoundTile = null;
let syncingSoundState = false;

function filterGallery() {
  const query = (searchInput?.value || "").trim().toLowerCase();
  let visibleCount = 0;

  for (const tile of tiles) {
    const name = tile.dataset.name || "";
    const tags = tile.dataset.tags || "";
    const matchesText = !query || name.includes(query);
    const matchesFilter = activeFilter === "all" || tags.includes(activeFilter);
    const visible = matchesText && matchesFilter;

    tile.hidden = !visible;
    if (visible) {
      visibleCount += 1;
    } else if (tile === activeSoundTile) {
      setSoundTile(null);
    }
  }

  if (emptyResult) {
    emptyResult.hidden = visibleCount !== 0;
  }
}

function getPlayableVideo(tile) {
  return tile.querySelector(".live-video");
}

function getSoundButton(tile) {
  return tile.querySelector("[data-sound-toggle]");
}

function updateSoundButton(button, enabled) {
  if (!button) {
    return;
  }

  button.setAttribute("aria-pressed", String(enabled));
  button.title = enabled ? "关闭声音" : "开启声音";
  const label = button.querySelector("span");
  if (label) {
    label.textContent = enabled ? "关闭声音" : "开启声音";
  }
}

function setSoundTile(nextTile) {
  syncingSoundState = true;
  for (const tile of tiles) {
    const video = getPlayableVideo(tile);
    const enabled = tile === nextTile;

    if (video) {
      video.muted = !enabled;
    }

    tile.classList.toggle("is-sound-on", enabled);
    updateSoundButton(getSoundButton(tile), enabled);
  }
  syncingSoundState = false;

  activeSoundTile = nextTile;

  if (nextTile) {
    playTile(nextTile);
  }
}

function playTile(tile) {
  const video = getPlayableVideo(tile);
  if (!video) {
    return;
  }

  tile.classList.add("is-playing");
  video.play().catch(() => {
    tile.classList.remove("is-playing");
  });
}

function pauseTile(tile) {
  const video = getPlayableVideo(tile);
  if (!video || video.classList.contains("is-primary") || tile.classList.contains("is-sound-on")) {
    return;
  }

  video.pause();
  video.currentTime = 0;
  tile.classList.remove("is-playing");
}

if (searchInput) {
  searchInput.addEventListener("input", filterGallery);
}

for (const button of filterButtons) {
  button.addEventListener("click", () => {
    activeFilter = button.dataset.filter || "all";
    for (const item of filterButtons) {
      item.classList.toggle("is-active", item === button);
    }
    filterGallery();
  });
}

for (const tile of tiles) {
  if (!tile.classList.contains("is-live")) {
    continue;
  }

  tile.addEventListener("mouseenter", () => playTile(tile));
  tile.addEventListener("mouseleave", () => pauseTile(tile));
  tile.addEventListener("focus", () => playTile(tile));
  tile.addEventListener("blur", () => pauseTile(tile));
  getPlayableVideo(tile)?.addEventListener("volumechange", () => {
    if (syncingSoundState) {
      return;
    }

    const video = getPlayableVideo(tile);
    if (!video) {
      return;
    }

    if (!video.muted) {
      setSoundTile(tile);
    } else if (tile === activeSoundTile) {
      setSoundTile(null);
    }
  });
  getSoundButton(tile)?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    setSoundTile(tile === activeSoundTile ? null : tile);
  });
  tile.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    if (tile.classList.contains("is-playing")) {
      pauseTile(tile);
    } else {
      playTile(tile);
    }
  });
}

filterGallery();
