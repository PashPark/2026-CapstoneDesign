const stateStyles = {
    HOT: {
        seat: "hot",
        text: "hot-text",
        message: "hot-message",
        border: "hot-border"
    },
    WARN: {
        seat: "warn",
        text: "warn-text",
        message: "warn-message",
        border: "warn-border"
    },
    OK: {
        seat: "empty",
        text: "ok-text",
        message: "ok-message",
        border: "ok-border"
    },
    "NO DETECT": {
        seat: "nodetect",
        text: "wait-text",
        message: "",
        border: ""
    },
    WAIT: {
        seat: "nodetect",
        text: "wait-text",
        message: "",
        border: ""
    }
};

let selectedSeatId = null;
let seatData = {};
let lastUpdateTime = null;
const seatIds = ["A1", "A2", "A3", "B1", "B2", "B3"];

function updateClock() {
    const liveClock = document.getElementById("liveClock");
    if (liveClock) {
        liveClock.innerText = new Date().toLocaleTimeString("en-GB", {
            timeZone: "Asia/Seoul"
        }) + " KST";
    }
}

function updateQrCode() {
    const qrImage = document.getElementById("pageQrImage");
    if (!qrImage) return;
    const currentUrl = window.location.href;
    qrImage.src =
        "https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=" +
        encodeURIComponent(currentUrl);
}

function updateSummary(data) {
    let detectedCount = 0;
    let okCount = 0;
    let warnCount = 0;
    let hotCount = 0;
    seatIds.forEach((seatId) => {
        const info = data[seatId];
        if (!info) return;
        const state = String(info.state || "NO DETECT").toUpperCase();
        if (state !== "NO DETECT" && state !== "WAIT" && state !== "") {
            detectedCount += 1;
        }
        if (state === "OK") okCount += 1;
        if (state === "WARN") warnCount += 1;
        if (state === "HOT") hotCount += 1;
    });
    const normalPercent = detectedCount > 0 ?
        Math.round((okCount / detectedCount) * 100) :
        0;
    document.getElementById("detectedSeatCount").innerText = detectedCount;
    document.getElementById("okCount").innerText = okCount;
    document.getElementById("warnCount").innerText = warnCount;
    document.getElementById("hotCount").innerText = hotCount;
    document.getElementById("normalPercent").innerText = normalPercent + "%";
    const riskCircle = document.getElementById("riskCircle");
    riskCircle.style.setProperty("--percent-deg", `${normalPercent * 3.6}deg`);
    const chip = document.getElementById("seatStatusChip");
    const chipText = document.getElementById("seatChipText");
    const chipIcon = document.getElementById("seatChipIcon");
    chip.className = "seat-chip";
    if (hotCount > 0) {
        chip.classList.add("danger");
        chipIcon.innerText = "!";
        chipText.innerText = `위험 좌석 ${hotCount}개 감지`;
    } else if (warnCount > 0) {
        chip.classList.add("warning");
        chipIcon.innerText = "!";
        chipText.innerText = `주의 좌석 ${warnCount}개 감지`;
    } else if (detectedCount === 6) {
        chipIcon.innerText = "✓";
        chipText.innerText = "모든 좌석 정상";
    } else if (detectedCount > 0) {
        chip.classList.add("warning");
        chipIcon.innerText = "!";
        chipText.innerText = `${detectedCount}개 좌석 인식 중`;
    } else {
        chip.classList.add("warning");
        chipIcon.innerText = "-";
        chipText.innerText = "좌석 인식 대기 중";
    }
    const sensorState = document.getElementById("sensorState");
    if (detectedCount > 0) {
        sensorState.innerText = "정상";
    } else {
        sensorState.innerText = "대기";
    }
}

function updateSystemInfo() {
    const updateTime = document.getElementById("updateTime");
    if (lastUpdateTime) {
        updateTime.innerText = lastUpdateTime;
    } else {
        updateTime.innerText = "--:--:--";
    }
}

function openSeatPanel(seatId) {
    selectedSeatId = seatId;
    const panel = document.getElementById("sidePanel");
    panel.classList.remove("left-mode");
    panel.classList.remove("right-mode");
    if (seatId === "A1" || seatId === "B1") {
        panel.classList.add("left-mode");
    } else {
        panel.classList.add("right-mode");
    }
    panel.classList.add("open");
    updateActiveSeat();
    updateSidePanel();
}

function closeSeatPanel() {
    selectedSeatId = null;
    document.getElementById("sidePanel").classList.remove("open");
    updateActiveSeat();
}

function updateActiveSeat() {
    seatIds.forEach((seatId) => {
        const seat = document.getElementById(seatId);
        if (!seat) return;
        if (seatId === selectedSeatId) {
            seat.classList.add("active-seat");
        } else {
            seat.classList.remove("active-seat");
        }
    });
}

function updateSidePanel() {
    if (!selectedSeatId) return;
    const info = seatData[selectedSeatId];
    const panelTitle = document.getElementById("panelTitle");
    const panelSubtitle = document.getElementById("panelSubtitle");
    const panelState = document.getElementById("panelState");
    const panelMessage = document.getElementById("panelMessage");
    const panelMaxHeat = document.getElementById("panelMaxHeat");
    const panelMeanHeat = document.getElementById("panelMeanHeat");
    const panelObject = document.getElementById("panelObject");
    const panelSeat = document.getElementById("panelSeat");
    const panelImageBox = document.getElementById("panelImageBox");
    panelTitle.innerText = selectedSeatId + " 좌석 상세 정보";
    panelSubtitle.innerText = "선택한 좌석의 실시간 발열 상태";
    if (!info) {
        panelState.innerText = "NO DETECT";
        panelState.className = "panel-state wait-text";
        panelMessage.innerText = "좌석 정보를 기다리는 중입니다.";
        panelMessage.className = "panel-message";
        panelMaxHeat.innerText = "0";
        panelMeanHeat.innerText = "0";
        panelObject.innerText = "-";
        panelSeat.innerText = selectedSeatId;
        panelImageBox.className = "panel-image-box";
        panelImageBox.innerHTML = "좌석 crop 영상을 기다리는 중입니다.";
        return;
    }
    const state = String(info.state || "NO DETECT").toUpperCase();
    const maxHeat = Number(info.max_heat || 0).toFixed(1);
    const meanHeat = Number(info.mean_heat || 0).toFixed(1);
    const hotObject = info.hot_object || "-";
    const cropImage = info.crop_image || "";
    panelState.innerText = state;
    panelState.className = ("panel-state " + (stateStyles[state] || stateStyles["NO DETECT"]).text);
    panelMessage.className = ("panel-message " + (stateStyles[state] || stateStyles["NO DETECT"]).message);
    if (state === "HOT") {
        panelMessage.innerText = info.warning_message && info.warning_message.length > 0 ?
            "⚠ " + info.warning_message :
            "⚠ 발열 위험 상태가 감지되었습니다.";
    } else if (state === "WARN") {
        panelMessage.innerText = info.warning_message && info.warning_message.length > 0 ?
            "⚠ " + info.warning_message :
            "⚠ 주의 온도가 감지되었습니다.";
    } else if (state === "OK") {
        panelMessage.innerText = info.warning_message && info.warning_message.length > 0 ?
            "✓ " + info.warning_message :
            "✓ 좌석 상태가 정상입니다.";
    } else {
        panelMessage.innerText = "좌석 인식을 기다리는 중입니다.";
    }
    panelMaxHeat.innerText = maxHeat + " ℃";
    panelMeanHeat.innerText = meanHeat + " ℃";
    panelObject.innerText = hotObject;
    panelSeat.innerText = selectedSeatId;
    if (cropImage.length > 30) {
        panelImageBox.className = ("panel-image-box " + (stateStyles[state] || stateStyles["NO DETECT"]).border);
        let image = panelImageBox.querySelector("img");
        if (!image) {
            image = document.createElement("img");
            panelImageBox.replaceChildren(image);
        }
        if (image.getAttribute("src") !== cropImage) image.src = cropImage;
        image.alt = selectedSeatId + " crop image";
    } else {
        panelImageBox.className = "panel-image-box";
        panelImageBox.innerHTML = "좌석 crop 영상을 기다리는 중입니다.";
    }
}
async function updateSeats() {
    try {
        const response = await fetch("/seat_status");
        const data = await response.json();
        seatData = data;
        lastUpdateTime = new Date().toLocaleTimeString("en-GB", {
            timeZone: "Asia/Seoul"
        });
        seatIds.forEach((seatId) => {
            const seat = document.getElementById(seatId);
            const info = data[seatId];
            if (!seat || !info) return;
            const state = String(info.state || "NO DETECT").toUpperCase();
            const maxHeat = Number(info.max_heat || 0).toFixed(1);
            const hotObject = info.hot_object || "-";
            const isActive = seatId === selectedSeatId;
            seat.className = "seat-overlay " + ((stateStyles[state] || stateStyles["NO DETECT"]).seat);
            if (isActive) {
                seat.classList.add("active-seat");
            }
            seat.innerHTML = `
 <div class="seat-code">${seatId}</div>
<div class="seat-status">${state}</div>
<div class="seat-heat">${maxHeat}℃ / ${hotObject}</div>
 `;
        });
        updateSummary(data);
        updateSystemInfo();
        updateSidePanel();
        const connectState = document.getElementById("connectState");
        if (connectState) {
            connectState.innerHTML = '<span class="online-dot"></span>온라인';
        }
    } catch (error) {
        console.log("seat update error:", error);
        const connectState = document.getElementById("connectState");
        if (connectState) {
            connectState.innerText = "연결 오류";
        }
    }
}
setInterval(updateClock, 1000);
setInterval(updateSeats, 300);
updateClock();
updateSeats();
updateQrCode();
