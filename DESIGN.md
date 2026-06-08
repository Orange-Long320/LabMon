# Design

## Overview

LabMon 是安静工具型 dashboard。界面服务于快速判断服务器资源状态，强调密度、秩序、明确状态和稳定布局。

## Color

Use OKLCH tokens only.

```css
:root {
  --bg: oklch(1.000 0.000 0);
  --surface: oklch(0.975 0.004 200);
  --surface-strong: oklch(0.942 0.007 200);
  --ink: oklch(0.210 0.018 215);
  --muted: oklch(0.435 0.022 215);
  --line: oklch(0.885 0.010 205);
  --primary: oklch(0.450 0.074 200);
  --primary-soft: oklch(0.925 0.035 200);
  --accent: oklch(0.590 0.135 150);
  --warning: oklch(0.650 0.150 70);
  --danger: oklch(0.560 0.170 25);
  --success: oklch(0.545 0.130 150);
}
```

Primary color is mineral teal, used for active state, links, and core affordances. Status colors are semantic and paired with text labels.

## Typography

Use `Inter`, `ui-sans-serif`, `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `sans-serif`. Use fixed rem sizes, not fluid type. Use tabular numbers for metrics and process tables.

## Layout

Desktop uses a top status bar, GPU lanes in the main column, and a right rail for host resources and logs. Mobile collapses into one column. Cards use 8px radius, light borders, no decorative wide shadows, no nested cards.

## Components

- GPU lane: status header, utilization bars, thermal/power strip, process table.
- Resource meter: label, numeric value, compact progress bar.
- Log row: file identity, parsed progress chips, tail button.
- Warning banner: plain filled tint with icon/text, not a side stripe.

## Motion

Use short 150-200ms transitions for hover, focus, and refresh state only. Respect `prefers-reduced-motion: reduce`.
