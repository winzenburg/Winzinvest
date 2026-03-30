'use client';

import React, { useId, useState, useRef, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';

const SHOW_DELAY_MS = 100;
/** Max bubble width; clamp center X so bubble stays inside viewport */
const TOOLTIP_MAX_WIDTH_PX = 280;
const VIEWPORT_MARGIN_PX = 12;

function clampTooltipCenterX(centerX: number): number {
  if (typeof window === 'undefined') return centerX;
  const vw = window.innerWidth;
  const half = Math.min(TOOLTIP_MAX_WIDTH_PX / 2, (vw - 2 * VIEWPORT_MARGIN_PX) / 2);
  return Math.min(
    Math.max(centerX, VIEWPORT_MARGIN_PX + half),
    vw - VIEWPORT_MARGIN_PX - half,
  );
}

interface TooltipProps {
  /** Tooltip content (plain text or short phrase). */
  text: string;
  /** Trigger element. Use a single child that can receive ref and event handlers. */
  children: React.ReactElement;
  /** Optional class for the trigger wrapper. */
  className?: string;
  /** Where to show tooltip relative to trigger: above (default) or below. */
  placement?: 'above' | 'below';
}

/**
 * Tooltip rendered via portal + fixed positioning so it is not clipped by
 * overflow-x-auto / overflow-hidden ancestors (e.g. positions table).
 */
export default function Tooltip({ text, children, className = '', placement = 'above' }: TooltipProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState<{ left: number; top: number } | null>(null);
  const showTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLSpanElement>(null);

  const clearShowTimeout = useCallback(() => {
    if (showTimeoutRef.current) {
      clearTimeout(showTimeoutRef.current);
      showTimeoutRef.current = null;
    }
  }, []);

  const updatePosition = useCallback(() => {
    const el = wrapRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const gap = 6;
    const rawCenter = r.left + r.width / 2;
    const left = clampTooltipCenterX(rawCenter);
    if (placement === 'above') {
      setCoords({ left, top: r.top - gap });
    } else {
      setCoords({ left, top: r.bottom + gap });
    }
  }, [placement]);

  const handleEnter = useCallback(() => {
    clearShowTimeout();
    showTimeoutRef.current = setTimeout(() => {
      updatePosition();
      setVisible(true);
    }, SHOW_DELAY_MS);
  }, [clearShowTimeout, updatePosition]);

  const handleLeave = useCallback(() => {
    clearShowTimeout();
    setVisible(false);
    setCoords(null);
  }, [clearShowTimeout]);

  const handleFocus = useCallback(() => {
    updatePosition();
    setVisible(true);
  }, [updatePosition]);

  const handleBlur = useCallback(() => {
    setVisible(false);
    setCoords(null);
  }, []);

  useEffect(() => {
    if (!visible) return;
    const onScrollResize = () => updatePosition();
    window.addEventListener('scroll', onScrollResize, true);
    window.addEventListener('resize', onScrollResize);
    return () => {
      window.removeEventListener('scroll', onScrollResize, true);
      window.removeEventListener('resize', onScrollResize);
    };
  }, [visible, updatePosition]);

  const trigger = React.cloneElement(children, {
    'aria-describedby': visible ? id : undefined,
    onMouseEnter: (e: React.MouseEvent) => {
      handleEnter();
      children.props.onMouseEnter?.(e);
    },
    onMouseLeave: (e: React.MouseEvent) => {
      handleLeave();
      children.props.onMouseLeave?.(e);
    },
    onFocus: (e: React.FocusEvent) => {
      handleFocus();
      children.props.onFocus?.(e);
    },
    onBlur: (e: React.FocusEvent) => {
      handleBlur();
      children.props.onBlur?.(e);
    },
    tabIndex: children.props.tabIndex ?? 0,
    className: [children.props.className, 'cursor-help', className].filter(Boolean).join(' '),
  });

  const bubble =
    visible &&
    text &&
    coords &&
    typeof document !== 'undefined' &&
    createPortal(
      <span
        id={id}
        role="tooltip"
        className="fixed z-[99999] box-border block px-3 py-2 text-left text-xs leading-relaxed text-white bg-slate-800 rounded shadow-lg whitespace-normal pointer-events-none break-words"
        style={{
          left: coords.left,
          top: coords.top,
          maxWidth: `min(${TOOLTIP_MAX_WIDTH_PX}px, calc(100vw - ${VIEWPORT_MARGIN_PX * 2}px))`,
          overflowWrap: 'anywhere',
          transform: placement === 'above' ? 'translate(-50%, -100%)' : 'translate(-50%, 0)',
        }}
      >
        {text}
      </span>,
      document.body,
    );

  return (
    <span ref={wrapRef} className="inline-block">
      {trigger}
      {bubble}
    </span>
  );
}
