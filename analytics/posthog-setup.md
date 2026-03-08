# PostHog Analytics Setup

**Project Token:** phc_xOzbNL7vMBFgbZshZEcs3LIvAwBjNvQLVo0bERsv53k  
**Project ID:** 244593

---

## PostHog Snippet (Add to <head> of all pages)

```html
<script>
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]]),t[o.length-1]]=e}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host.replace(".js","")+"/decide/?v=3",p.onload=function(){if(e.decide)e.decide()},(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);try{e._i.push(function(){var t;((t=window.posthog).__loaded=!0).config(i,s),e.capture_pageview()})}catch(t){console.error("PostHog script load failed:",t)}},e.__loaded=!0)}(document,window.posthog||[]);
  posthog.init('phc_xOzbNL7vMBFgbZshZEcs3LIvAwBjNvQLVo0bERsv53k',{
    api_host:'https://us.posthog.com',
    person_profiles: 'identified_only'
  })
</script>
```

---

## Projects to Instrument

### 1. kinlet.care (Pre-launch Waitlist)
**Events to track:**
- Page view
- Scroll depth (%) at intervals (25%, 50%, 75%, 100%)
- Form field interaction (email, relationship, stage)
- Form submission (waitlist signup)
- CTA click

### 2. kinetic-ui.com (Pre-launch Early Access)
**Events to track:**
- Page view
- Scroll depth (%) at intervals
- "How it works" section view
- Early access form interaction
- Form submission
- Founder slots view

### 3. winzenburg.com (Mature Consulting Site)
**Events to track:**
- Page view
- CTA click ("Schedule a Call", "Contact")
- Article engagement (scroll depth, time on page)
- Navigation clicks (Work, Services, Methodology)
- Return visitor identification

### 4. Potshards (Substack Newsletter)
**Note:** Substack handles its own analytics. PostHog not needed here.

---

## PostHog Event Configuration

After embedding, configure these custom events in PostHog:

```javascript
// Waitlist form submission
posthog.capture('waitlist_signup', {
  email: user_email,
  relationship: relationship_value,
  stage: stage_value
});

// CTA clicks
posthog.capture('cta_click', {
  cta_text: 'Schedule a Call',
  page: window.location.pathname
});

// Scroll depth
window.addEventListener('scroll', function() {
  const scrollPercent = (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100;
  if (scrollPercent >= 25 && !window.posthog_25) {
    window.posthog_25 = true;
    posthog.capture('scroll_depth', { depth: 25 });
  }
  // ... repeat for 50%, 75%, 100%
});
```

---

## Mission Control Integration

Once PostHog is live:
- Pull conversion rates: `waitlist_signup / page_view`
- Pull traffic sources: `$initial_utm_source` by device
- Pull scroll engagement: `scroll_depth` percentage distribution
- Pull form abandonment: Form interactions without submission

---

## Status

- [ ] kinlet.care — PostHog embedded
- [ ] kinetic-ui.com — PostHog embedded  
- [ ] winzenburg.com — PostHog embedded
- [ ] Mission Control connectors built
