// ---------- Setup ----------
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
ctx.imageSmoothingEnabled = false;

const TILE = 32;
const GRAVITY = 0.55;
const MAX_FALL_SPEED = 14;

const TILE_EMPTY = 0;
const TILE_GROUND = 1;
const TILE_BRICK = 2;
const TILE_QBLOCK_COIN = 3;
const TILE_QBLOCK_MUSHROOM = 4;
const TILE_USED_BLOCK = 5;
const TILE_PIPE = 6;
const TILE_FLAGPOLE = 7;
const TILE_FLAGPOLE_TOP = 8;

const SOLID_TILES = new Set([
  TILE_GROUND, TILE_BRICK, TILE_QBLOCK_COIN, TILE_QBLOCK_MUSHROOM, TILE_USED_BLOCK, TILE_PIPE,
]);

// ---------- Level ----------
function buildLevel() {
  const width = 130;
  const height = 15;
  const grid = Array.from({ length: height }, () => new Array(width).fill(TILE_EMPTY));

  const groundRows = [13, 14];
  const pits = [[24, 26], [55, 57], [88, 91]];
  const isPit = (col) => pits.some(([a, b]) => col >= a && col <= b);

  for (let col = 0; col < width; col++) {
    if (isPit(col)) continue;
    for (const row of groundRows) grid[row][col] = TILE_GROUND;
  }

  const blocks = [
    { col: 16, row: 10, type: TILE_QBLOCK_COIN },
    { col: 20, row: 10, type: TILE_QBLOCK_MUSHROOM },
    { col: 21, row: 10, type: TILE_BRICK },
    { col: 22, row: 10, type: TILE_QBLOCK_COIN },
    { col: 35, row: 9, type: TILE_BRICK },
    { col: 36, row: 9, type: TILE_QBLOCK_COIN },
    { col: 37, row: 9, type: TILE_BRICK },
    { col: 63, row: 10, type: TILE_QBLOCK_MUSHROOM },
    { col: 78, row: 8, type: TILE_QBLOCK_COIN },
  ];
  for (const b of blocks) grid[b.row][b.col] = b.type;

  const pipes = [
    { col: 12, h: 2 },
    { col: 45, h: 3 },
    { col: 75, h: 2 },
    { col: 100, h: 4 },
  ];
  for (const p of pipes) {
    for (let i = 0; i < p.h; i++) {
      const row = 13 - i;
      if (!isPit(p.col)) grid[row][p.col] = TILE_PIPE;
    }
  }

  // staircase near the end
  for (let i = 0; i < 6; i++) {
    for (let j = 0; j <= i; j++) {
      grid[13 - j][108 + i] = TILE_GROUND;
    }
  }

  const flagCol = width - 6;
  for (let row = 5; row <= 12; row++) grid[row][flagCol] = TILE_FLAGPOLE;
  grid[4][flagCol] = TILE_FLAGPOLE_TOP;

  const coins = [];
  for (const c of [
    [17, 9], [18, 9], [19, 9],
    [30, 11], [31, 9], [32, 9], [33, 11],
    [60, 9], [61, 9], [62, 9],
    [95, 9], [96, 9], [97, 9], [98, 9],
  ]) coins.push({ col: c[0], row: c[1], taken: false, bob: Math.random() * Math.PI * 2 });

  const enemies = [
    { col: 14, type: "goomba" },
    { col: 27, type: "goomba" },
    { col: 38, type: "goomba" },
    { col: 50, type: "goomba" },
    { col: 51, type: "goomba" },
    { col: 65, type: "goomba" },
    { col: 80, type: "goomba" },
    { col: 92, type: "goomba" },
    { col: 93, type: "goomba" },
    { col: 112, type: "goomba" },
  ];

  return { grid, width, height, coins, enemyDefs: enemies, flagCol };
}

// ---------- Entities ----------
function makeGoomba(col) {
  return {
    type: "goomba",
    x: col * TILE,
    y: 13 * TILE - 28,
    w: 28,
    h: 28,
    vx: -1.2,
    vy: 0,
    alive: true,
    squished: 0,
  };
}

function makeMushroom(x, y) {
  return { x, y, w: 26, h: 26, vx: 1.5, vy: 0, alive: true, emerging: 6 };
}

function tileAt(grid, col, row) {
  if (row < 0 || row >= grid.length || col < 0 || col >= grid[0].length) return TILE_GROUND;
  return grid[row][col];
}

function isSolid(tile) {
  return SOLID_TILES.has(tile);
}

// ---------- Game state ----------
let level, player, enemies, mushrooms, particles, camera, keys, gameState, score, coinCount, lives;

function resetGame(fullReset) {
  level = buildLevel();
  player = {
    x: 2 * TILE,
    y: 11 * TILE,
    w: 26,
    h: 30,
    vx: 0,
    vy: 0,
    onGround: false,
    facing: 1,
    big: false,
    invincible: 0,
    dead: false,
    winTimer: 0,
  };
  enemies = level.enemyDefs.map((e) => makeGoomba(e.col));
  mushrooms = [];
  particles = [];
  camera = { x: 0 };
  keys = keys || {};
  gameState = "playing";
  if (fullReset) {
    score = 0;
    coinCount = 0;
    lives = 3;
  }
  updateHud();
  hideOverlay();
}

function updateHud() {
  document.getElementById("score").textContent = score;
  document.getElementById("coins").textContent = coinCount;
  document.getElementById("lives").textContent = lives;
}

function showOverlay(title, text) {
  document.getElementById("overlay-title").textContent = title;
  document.getElementById("overlay-text").textContent = text;
  document.getElementById("overlay").classList.remove("hidden");
}
function hideOverlay() {
  document.getElementById("overlay").classList.add("hidden");
}

// ---------- Input ----------
keys = {};
window.addEventListener("keydown", (e) => {
  keys[e.code] = true;
  if (e.code === "KeyR") resetGame(true);
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) e.preventDefault();
});
window.addEventListener("keyup", (e) => {
  keys[e.code] = false;
});
document.getElementById("overlay-btn").addEventListener("click", () => resetGame(true));

// ---------- Collision helpers ----------
function moveAndCollide(entity, grid) {
  // horizontal
  entity.x += entity.vx;
  resolveAxis(entity, grid, "x");
  // vertical
  entity.y += entity.vy;
  entity.onGround = false;
  resolveAxis(entity, grid, "y");
}

function resolveAxis(entity, grid, axis) {
  const left = Math.floor(entity.x / TILE);
  const right = Math.floor((entity.x + entity.w - 1) / TILE);
  const top = Math.floor(entity.y / TILE);
  const bottom = Math.floor((entity.y + entity.h - 1) / TILE);

  for (let row = top; row <= bottom; row++) {
    for (let col = left; col <= right; col++) {
      const tile = tileAt(grid, col, row);
      if (!isSolid(tile)) continue;
      const tx = col * TILE;
      const ty = row * TILE;

      if (axis === "x") {
        if (entity.vx > 0) entity.x = tx - entity.w;
        else if (entity.vx < 0) entity.x = tx + TILE;
        entity.vx = 0;
      } else {
        if (entity.vy > 0) {
          entity.y = ty - entity.h;
          entity.vy = 0;
          entity.onGround = true;
        } else if (entity.vy < 0) {
          entity.y = ty + TILE;
          entity.vy = 0;
          if (entity === player) onBlockHit(col, row);
        }
      }
    }
  }
}

function onBlockHit(col, row) {
  const tile = level.grid[row][col];
  if (tile === TILE_QBLOCK_COIN) {
    level.grid[row][col] = TILE_USED_BLOCK;
    score += 100;
    coinCount += 1;
    updateHud();
    spawnPopup(col * TILE + TILE / 2, row * TILE, "+100");
  } else if (tile === TILE_QBLOCK_MUSHROOM) {
    level.grid[row][col] = TILE_USED_BLOCK;
    mushrooms.push(makeMushroom(col * TILE, row * TILE - TILE));
  } else if (tile === TILE_BRICK) {
    if (player.big) {
      level.grid[row][col] = TILE_EMPTY;
      score += 50;
      updateHud();
      spawnPopup(col * TILE + TILE / 2, row * TILE, "+50");
    } else {
      spawnPopup(col * TILE + TILE / 2, row * TILE, "*bonk*");
    }
  }
}

function spawnPopup(x, y, text) {
  particles.push({ x, y, text, life: 40 });
}

// ---------- Update ----------
function updatePlayer() {
  if (gameState !== "playing") return;

  const speedCap = keys["ShiftLeft"] || keys["ShiftRight"] ? 5.2 : 3.6;
  const accel = 0.4;
  const friction = 0.45;
  const left = keys["ArrowLeft"] || keys["KeyA"];
  const right = keys["ArrowRight"] || keys["KeyD"];
  const jumpPressed = keys["Space"] || keys["ArrowUp"] || keys["KeyW"];

  if (left && !right) {
    player.vx -= accel;
    player.facing = -1;
  } else if (right && !left) {
    player.vx += accel;
    player.facing = 1;
  } else {
    if (player.vx > 0) player.vx = Math.max(0, player.vx - friction);
    else if (player.vx < 0) player.vx = Math.min(0, player.vx + friction);
  }
  player.vx = Math.max(-speedCap, Math.min(speedCap, player.vx));

  if (jumpPressed && player.onGround && !player.jumping) {
    player.vy = -10.5;
    player.jumping = true;
    player.onGround = false;
  }
  if (!jumpPressed) player.jumping = false;
  if (!jumpPressed && player.vy < -4) player.vy = -4; // variable jump height

  player.vy = Math.min(MAX_FALL_SPEED, player.vy + GRAVITY);

  moveAndCollide(player, level.grid);

  if (player.x < 0) player.x = 0;
  if (player.invincible > 0) player.invincible--;

  // coins
  for (const c of level.coins) {
    if (c.taken) continue;
    const cx = c.col * TILE, cy = c.row * TILE;
    if (rectsOverlap(player.x, player.y, player.w, player.h, cx + 4, cy + 4, TILE - 8, TILE - 8)) {
      c.taken = true;
      score += 10;
      coinCount += 1;
      updateHud();
    }
  }

  // mushrooms
  for (const m of mushrooms) {
    if (!m.alive) continue;
    if (rectsOverlap(player.x, player.y, player.w, player.h, m.x, m.y, m.w, m.h)) {
      m.alive = false;
      if (!player.big) {
        player.big = true;
        player.h = 52;
        player.y -= 22;
      }
      score += 1000;
      updateHud();
    }
  }

  // enemy collisions
  for (const en of enemies) {
    if (!en.alive) continue;
    if (!rectsOverlap(player.x, player.y, player.w, player.h, en.x, en.y, en.w, en.h)) continue;
    const playerBottom = player.y + player.h;
    const stomping = player.vy > 0 && playerBottom - en.y < 16;
    if (stomping) {
      en.alive = false;
      en.squished = 20;
      player.vy = -6.5;
      score += 200;
      updateHud();
      spawnPopup(en.x + en.w / 2, en.y, "+200");
    } else if (player.invincible === 0) {
      hurtPlayer();
    }
  }

  // falling into pit
  if (player.y > level.height * TILE + 100) {
    killPlayer();
  }

  // flagpole
  const flagX = level.flagCol * TILE;
  if (gameState === "playing" && player.x + player.w > flagX && player.x < flagX + TILE) {
    winLevel();
  }
}

function hurtPlayer() {
  if (player.big) {
    player.big = false;
    player.h = 30;
    player.invincible = 90;
  } else {
    killPlayer();
  }
}

function killPlayer() {
  if (gameState !== "playing") return;
  gameState = "dead";
  lives -= 1;
  updateHud();
  setTimeout(() => {
    if (lives <= 0) {
      showOverlay("Game Over", `Punktestand: ${score}`);
    } else {
      resetGame(false);
    }
  }, 900);
}

function winLevel() {
  gameState = "won";
  showOverlay("Level geschafft!", `Punktestand: ${score} — Drücke Neustart für eine neue Runde.`);
}

function rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh) {
  return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

function updateEnemies() {
  for (const en of enemies) {
    if (!en.alive) {
      if (en.squished > 0) en.squished--;
      continue;
    }
    en.vy = Math.min(MAX_FALL_SPEED, en.vy + GRAVITY);
    const prevVx = en.vx;
    moveAndCollide(en, level.grid);
    if (en.vx === 0) en.vx = -prevVx || -1.2;

    const aheadCol = Math.floor((en.x + (en.vx > 0 ? en.w + 1 : -1)) / TILE);
    const belowRow = Math.floor((en.y + en.h + 1) / TILE);
    if (!isSolid(tileAt(level.grid, aheadCol, belowRow))) {
      en.vx *= -1;
    }
  }
}

function updateMushrooms() {
  for (const m of mushrooms) {
    if (!m.alive) continue;
    if (m.emerging > 0) {
      m.emerging--;
      continue;
    }
    m.vy = Math.min(MAX_FALL_SPEED, m.vy + GRAVITY);
    const prevVx = m.vx;
    moveAndCollide(m, level.grid);
    if (m.vx === 0) m.vx = -prevVx || 1.5;
  }
}

function updateCamera() {
  const targetX = player.x - canvas.width / 2 + player.w / 2;
  const maxX = level.width * TILE - canvas.width;
  camera.x = Math.max(0, Math.min(maxX, targetX));
}

function updateParticles() {
  for (const p of particles) {
    p.y -= 0.5;
    p.life--;
  }
  particles = particles.filter((p) => p.life > 0);
}

// ---------- Render ----------
function drawBackground() {
  ctx.fillStyle = "#5c94fc";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "rgba(255,255,255,0.85)";
  for (let i = 0; i < 6; i++) {
    const x = ((i * 260 - camera.x * 0.3) % (level.width * TILE + 300)) - 100;
    drawCloud(x, 40 + (i % 3) * 25);
  }

  ctx.fillStyle = "#3fae3f";
  for (let i = 0; i < 10; i++) {
    const x = ((i * 320 - camera.x * 0.6) % (level.width * TILE + 300)) - 100;
    drawHill(x, 420);
  }
}

function drawCloud(x, y) {
  ctx.beginPath();
  ctx.arc(x, y, 16, 0, Math.PI * 2);
  ctx.arc(x + 18, y - 8, 18, 0, Math.PI * 2);
  ctx.arc(x + 38, y, 16, 0, Math.PI * 2);
  ctx.fill();
}

function drawHill(x, y) {
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + 60, y - 40);
  ctx.lineTo(x + 120, y);
  ctx.closePath();
  ctx.fill();
}

function drawTiles() {
  const startCol = Math.floor(camera.x / TILE);
  const endCol = Math.min(level.width - 1, startCol + Math.ceil(canvas.width / TILE) + 1);

  for (let row = 0; row < level.height; row++) {
    for (let col = startCol; col <= endCol; col++) {
      const tile = level.grid[row][col];
      if (tile === TILE_EMPTY) continue;
      const x = col * TILE - camera.x;
      const y = row * TILE;
      drawTile(tile, x, y);
    }
  }
}

function drawTile(tile, x, y) {
  switch (tile) {
    case TILE_GROUND:
      ctx.fillStyle = "#c87137";
      ctx.fillRect(x, y, TILE, TILE);
      ctx.fillStyle = "#3fae3f";
      ctx.fillRect(x, y, TILE, 6);
      ctx.strokeStyle = "rgba(0,0,0,0.15)";
      ctx.strokeRect(x + 0.5, y + 0.5, TILE - 1, TILE - 1);
      break;
    case TILE_BRICK:
      ctx.fillStyle = "#b5651d";
      ctx.fillRect(x, y, TILE, TILE);
      ctx.strokeStyle = "rgba(0,0,0,0.35)";
      ctx.strokeRect(x + 1, y + 1, TILE / 2 - 1, TILE / 2 - 1);
      ctx.strokeRect(x + TILE / 2, y + 1, TILE / 2 - 1, TILE / 2 - 1);
      ctx.strokeRect(x + 1, y + TILE / 2, TILE / 2 - 1, TILE / 2 - 1);
      ctx.strokeRect(x + TILE / 2, y + TILE / 2, TILE / 2 - 1, TILE / 2 - 1);
      break;
    case TILE_QBLOCK_COIN:
    case TILE_QBLOCK_MUSHROOM:
      ctx.fillStyle = "#ffd23f";
      ctx.fillRect(x, y, TILE, TILE);
      ctx.strokeStyle = "rgba(0,0,0,0.4)";
      ctx.strokeRect(x + 1.5, y + 1.5, TILE - 3, TILE - 3);
      ctx.fillStyle = "#8a5a00";
      ctx.font = "bold 18px monospace";
      ctx.textAlign = "center";
      ctx.fillText("?", x + TILE / 2, y + TILE / 2 + 7);
      break;
    case TILE_USED_BLOCK:
      ctx.fillStyle = "#946638";
      ctx.fillRect(x, y, TILE, TILE);
      ctx.strokeStyle = "rgba(0,0,0,0.25)";
      ctx.strokeRect(x + 0.5, y + 0.5, TILE - 1, TILE - 1);
      break;
    case TILE_PIPE:
      ctx.fillStyle = "#2f9e2f";
      ctx.fillRect(x + 2, y, TILE - 4, TILE);
      ctx.strokeStyle = "rgba(0,0,0,0.3)";
      ctx.strokeRect(x + 2, y, TILE - 4, TILE);
      break;
    case TILE_FLAGPOLE:
      ctx.fillStyle = "#cccccc";
      ctx.fillRect(x + TILE / 2 - 2, y, 4, TILE);
      break;
    case TILE_FLAGPOLE_TOP: {
      ctx.fillStyle = "#cccccc";
      ctx.fillRect(x + TILE / 2 - 2, y, 4, TILE);
      ctx.fillStyle = "#e63946";
      ctx.beginPath();
      ctx.moveTo(x + TILE / 2 + 2, y + 4);
      ctx.lineTo(x + TILE / 2 + 22, y + 10);
      ctx.lineTo(x + TILE / 2 + 2, y + 16);
      ctx.closePath();
      ctx.fill();
      break;
    }
  }
}

function drawCoins() {
  for (const c of level.coins) {
    if (c.taken) continue;
    c.bob += 0.12;
    const x = c.col * TILE - camera.x + TILE / 2;
    const y = c.row * TILE + TILE / 2 + Math.sin(c.bob) * 3;
    const squeeze = Math.abs(Math.cos(c.bob * 0.7));
    ctx.fillStyle = "#ffd23f";
    ctx.beginPath();
    ctx.ellipse(x, y, 8 * squeeze + 2, 10, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#a97a00";
    ctx.stroke();
  }
}

function drawMushroom(m) {
  const x = m.x - camera.x;
  const y = m.y;
  ctx.fillStyle = "#e63946";
  ctx.beginPath();
  ctx.arc(x + m.w / 2, y + m.h / 2 - 2, m.w / 2, Math.PI, 0);
  ctx.fill();
  ctx.fillStyle = "#fff3e0";
  ctx.fillRect(x + 4, y + m.h / 2 - 2, m.w - 8, m.h / 2);
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(x + 7, y + 8, 3, 0, Math.PI * 2);
  ctx.arc(x + m.w - 7, y + 8, 3, 0, Math.PI * 2);
  ctx.arc(x + m.w / 2, y + 5, 3, 0, Math.PI * 2);
  ctx.fill();
}

function drawGoomba(en) {
  const x = en.x - camera.x;
  const y = en.y;
  if (!en.alive) {
    ctx.fillStyle = "#7a4a2b";
    ctx.fillRect(x, y + en.h - 8, en.w, 8);
    return;
  }
  ctx.fillStyle = "#7a4a2b";
  ctx.beginPath();
  ctx.arc(x + en.w / 2, y + en.h / 2, en.w / 2, Math.PI, 0);
  ctx.fill();
  ctx.fillRect(x, y + en.h / 2, en.w, en.h / 2 - 4);
  ctx.fillStyle = "#3d2410";
  ctx.fillRect(x + 2, y + en.h - 6, 8, 6);
  ctx.fillRect(x + en.w - 10, y + en.h - 6, 8, 6);
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.arc(x + 9, y + en.h / 2 - 2, 4, 0, Math.PI * 2);
  ctx.arc(x + en.w - 9, y + en.h / 2 - 2, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.arc(x + 9, y + en.h / 2 - 2, 2, 0, Math.PI * 2);
  ctx.arc(x + en.w - 9, y + en.h / 2 - 2, 2, 0, Math.PI * 2);
  ctx.fill();
}

function drawPlayer() {
  const x = player.x - camera.x;
  const y = player.y;
  const w = player.w;
  const h = player.h;

  if (player.invincible > 0 && Math.floor(player.invincible / 4) % 2 === 0) return;

  ctx.save();
  ctx.translate(x + w / 2, y);
  ctx.scale(player.facing, 1);
  ctx.translate(-w / 2, 0);

  // cap
  ctx.fillStyle = "#e63946";
  ctx.fillRect(0, 0, w, h * 0.22);
  ctx.fillRect(-3, h * 0.14, w * 0.6, h * 0.1);
  // face
  ctx.fillStyle = "#ffd9a0";
  ctx.fillRect(2, h * 0.2, w - 4, h * 0.22);
  // overalls / body
  ctx.fillStyle = "#3a6bd8";
  ctx.fillRect(0, h * 0.42, w, h * 0.35);
  // shirt sleeves
  ctx.fillStyle = "#e63946";
  ctx.fillRect(0, h * 0.42, w, h * 0.14);
  // legs
  ctx.fillStyle = "#3a6bd8";
  ctx.fillRect(2, h * 0.78, w * 0.4, h * 0.22);
  ctx.fillRect(w * 0.55, h * 0.78, w * 0.4, h * 0.22);

  ctx.restore();
}

function drawParticles() {
  ctx.fillStyle = "#fff";
  ctx.font = "bold 14px monospace";
  ctx.textAlign = "center";
  for (const p of particles) {
    ctx.globalAlpha = Math.max(0, p.life / 40);
    ctx.fillText(p.text, p.x - camera.x, p.y);
  }
  ctx.globalAlpha = 1;
}

function render() {
  drawBackground();
  drawTiles();
  drawCoins();
  for (const m of mushrooms) if (m.alive) drawMushroom(m);
  for (const en of enemies) drawGoomba(en);
  if (gameState !== "dead" || Math.floor(Date.now() / 100) % 2 === 0) drawPlayer();
  drawParticles();
}

// ---------- Main loop ----------
function loop() {
  if (gameState === "playing") {
    updatePlayer();
    updateEnemies();
    updateMushrooms();
    updateParticles();
  }
  updateCamera();
  render();
  requestAnimationFrame(loop);
}

resetGame(true);
loop();
