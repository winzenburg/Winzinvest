'use client';

import React, { useId, useState, useRef, useCallback } from 'react';

const SHOW_DELAY_MS = 100;
const HIDE_DELAY_MS = 0;

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
 * Fast tooltip: shows after 100ms on hover, immediately on focus.
 * Avoids the slow native browser title delay.
 */
export default function Tooltip({ text, children, className = '', placement = 'above' }: TooltipProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const showTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearShowTimeout = useCallback(() => {
    if (showTimeoutRef.current) {
      clearTimeout(showTimeoutRef.current);
      showTimeoutRef.current = null;
    }
  }, []);

  const handleEnter = useCallback(() => {
    clearShowTimeout();
    showTimeoutRef.current = setTimeout(() => setVisible(true), SHOW_DELAY_MS);
  }, [clearShowTimeout]);

  const handleLeave = useCallback(() => {
    clearShowTimeout();
    setVisible(false);
  }, [clearShowTimeout]);

  const handleFocus = useCallback(() => setVisible(true), []);
  const handleBlur = useCallback(() => setVisible(false), []);

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

  return (
    <span className="relative inline-block">
      {trigger}
      {visible && text && (
        <span
          id={id}
          role="tooltip"
          className={`absolute left-1/2 -translate-x-1/2 z-50 px-2 py-1.5 text-xs text-white bg-slate-800 rounded shadow-lg whitespace-normal max-w-[440px] pointer-events-none ${
            placement === 'above'
              ? 'bottom-full mb-1.5'
              : 'top-full mt-1.5'
          }`}
        >
          {text}
        </span>
      )}
    </span>
  );
}
