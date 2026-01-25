# 🔭 NASA Telescopes - Search Reference for Download Tool

Quick reference guide for searching NASA telescope images and videos. Copy the telescope names below to use as search queries in the NASA Media Downloader.

---

## 📋 Quick Search Templates

### Copy-Paste Ready Search Queries

```bash
# Search for specific telescope
python nasa_downloader_v2.py --query "hubble space telescope"

# Search for telescope + subject
python nasa_downloader_v2.py --query "james webb deep field"

# Search for mission images
python nasa_downloader_v2.py --query "chandra x-ray nebula"
```

---

## 🌟 Great Observatories (Copy These Names)

**Most Popular - Guaranteed High-Quality Results**

```
Hubble Space Telescope
Hubble
HST
```

```
James Webb Space Telescope
James Webb
JWST
Webb Telescope
```

```
Chandra X-ray Observatory
Chandra
```

```
Spitzer Space Telescope
Spitzer
```

```
Compton Gamma Ray Observatory
CGRO
```

---

## 🚀 Active Telescopes (Currently Operational)

### Major Missions

**Exoplanet Hunters:**
```
TESS
Transiting Exoplanet Survey Satellite
```

**High-Energy Observatories:**
```
Fermi Gamma-ray Space Telescope
Fermi
```

```
NuSTAR
Nuclear Spectroscopic Telescope Array
```

```
NICER
Neutron star Interior Composition Explorer
```

```
Swift Observatory
Swift
```

```
IXPE
Imaging X-ray Polarimetry Explorer
```

**Solar Observers:**
```
IRIS
Interface Region Imaging Spectrograph
Solar Dynamics Observatory
SDO
```

---

## 🔜 Upcoming Telescopes

**Future Missions (Limited Current Content):**
```
Nancy Grace Roman Space Telescope
Roman Space Telescope
Nancy Roman
```

```
SPHEREx
```

---

## 📡 Historic/Retired Telescopes

**Legendary Missions with Extensive Archives:**

```
Kepler Space Telescope
Kepler
```

```
WISE
Wide-field Infrared Survey Explorer
NEOWISE
```

```
GALEX
Galaxy Evolution Explorer
```

```
COBE
Cosmic Background Explorer
```

```
IRAS
Infrared Astronomical Satellite
```

```
Einstein Observatory
HEAO-2
```

```
RXTE
Rossi X-ray Timing Explorer
```

---

## 🌍 International Partner Telescopes

**NASA-Contributed Missions:**

```
XRISM
X-ray Imaging and Spectroscopy Mission
```

```
XMM-Newton
```

```
Euclid Space Telescope
```

---

## 💡 Pro Search Tips

### Combine Telescope + Subject for Best Results

**Nebulae & Star Formation:**
```
Hubble Nebula
Spitzer Star Formation
James Webb Nebula
Chandra Supernova
```

**Galaxies:**
```
Hubble Deep Field
James Webb Galaxy
Spitzer Galaxy Cluster
Chandra Galaxy Collision
```

**Planets & Solar System:**
```
Hubble Jupiter
Hubble Mars
Hubble Saturn
TESS Exoplanet
```

**Black Holes & Extreme Objects:**
```
Chandra Black Hole
NuSTAR Pulsar
Fermi Gamma Ray Burst
```

**Exoplanets:**
```
TESS Exoplanet
Kepler Planet Discovery
Spitzer Exoplanet Atmosphere
```

---

## 🎯 Search Strategy Guide

### For Maximum Results:

**1. Start Broad, Then Narrow:**
```bash
# Broad search
python nasa_downloader_v2.py --query "Hubble"

# Narrow search  
python nasa_downloader_v2.py --query "Hubble Pillars of Creation"
```

**2. Use Official Names:**
```bash
# Better results
--query "Hubble Space Telescope"

# vs generic
--query "space telescope"
```

**3. Combine Multiple Terms:**
```bash
--query "James Webb Deep Field Galaxies"
--query "Chandra Crab Nebula X-ray"
--query "Kepler Exoplanet Discovery"
```

**4. Try Acronyms AND Full Names:**
```bash
--query "HST"
--query "Hubble Space Telescope"
# Both might return different images
```

---

## 📊 Telescope Categories by Content Type

### 🎨 **Best for Beautiful Visuals** (High Image Count)
- Hubble Space Telescope
- James Webb Space Telescope
- Spitzer Space Telescope

### 🔬 **Best for Scientific Data** (Specialized)
- Chandra X-ray Observatory
- Fermi Gamma-ray Telescope
- NuSTAR

### 🪐 **Best for Exoplanets**
- TESS
- Kepler Space Telescope
- Spitzer (exoplanet atmospheres)

### 🌌 **Best for Deep Space/Galaxies**
- Hubble (Deep Fields)
- James Webb (Early Universe)
- Spitzer (Infrared Galaxies)

### ☀️ **Best for Solar/Sun Images**
- IRIS
- Solar Dynamics Observatory

---

## 🔥 Top 10 Most Popular Searches

Copy these proven high-yield queries:

```
1. Hubble Space Telescope
2. James Webb Space Telescope
3. Hubble Deep Field
4. Pillars of Creation
5. Crab Nebula
6. Andromeda Galaxy Hubble
7. James Webb First Images
8. Chandra Supernova
9. Kepler Exoplanet
10. Spitzer Infrared
```

---

## 📝 Example Commands

### Download Top Hubble Images
```bash
python nasa_downloader_v2.py \
  --query "Hubble Space Telescope" \
  --images \
  --qualities orig \
  --limit 100 \
  --no-prompt
```

### Get Webb's Greatest Hits
```bash
python nasa_downloader_v2.py \
  --query "James Webb Deep Field" \
  --images \
  --qualities all \
  --metadata \
  --no-prompt
```

### Archive Kepler Discoveries
```bash
python nasa_downloader_v2.py \
  --query "Kepler Exoplanet" \
  --images \
  --videos \
  --qualities orig \
  --metadata \
  --limit 200 \
  --no-prompt
```

### Chandra X-ray Collection
```bash
python nasa_downloader_v2.py \
  --query "Chandra X-ray" \
  --images \
  --qualities large,orig \
  --no-prompt
```

---

## 🎓 Educational Collections

### Build Themed Collections:

**"Evolution of the Universe" Collection:**
```bash
# Ancient galaxies
--query "James Webb Early Universe"

# Galaxy formation
--query "Hubble Deep Field"

# Star birth
--query "Spitzer Star Formation"

# Star death
--query "Chandra Supernova Remnant"
```

**"Hunt for Other Worlds" Collection:**
```bash
--query "TESS Exoplanet Discovery"
--query "Kepler Planet Transit"
--query "Spitzer Exoplanet Atmosphere"
--query "Hubble Exoplanet"
```

**"Cosmic Catastrophes" Collection:**
```bash
--query "Chandra Supernova"
--query "Fermi Gamma Ray Burst"
--query "Hubble Galaxy Collision"
--query "NuSTAR Black Hole"
```

---

## 📌 Quick Reference Table

| Telescope | Best For | Search Term | Content Volume |
|-----------|----------|-------------|----------------|
| Hubble | Everything! | `Hubble` | ⭐⭐⭐⭐⭐ Massive |
| James Webb | Deep Space, Galaxies | `James Webb` | ⭐⭐⭐⭐ Growing |
| Chandra | X-ray Universe | `Chandra X-ray` | ⭐⭐⭐⭐ Large |
| Spitzer | Infrared, Exoplanets | `Spitzer` | ⭐⭐⭐⭐ Large |
| TESS | Exoplanets | `TESS Exoplanet` | ⭐⭐⭐ Medium |
| Kepler | Exoplanets | `Kepler` | ⭐⭐⭐ Medium |
| Fermi | Gamma Rays | `Fermi` | ⭐⭐ Moderate |
| NuSTAR | Black Holes | `NuSTAR` | ⭐⭐ Moderate |

---

## 🚀 Happy Downloading!

**Pro Tip:** Start with `Hubble Space Telescope` - it has the largest archive with the most visually stunning images!

```bash
python nasa_downloader_v2.py --query "Hubble Space Telescope" --images --qualities orig --limit 50
```

---

**Total Telescopes Available:** 30+  
**Most Content:** Hubble (~140,000 images)  
**Newest:** James Webb (2021-present)  
**Best Archive:** Hubble, Spitzer, Chandra, Kepler
