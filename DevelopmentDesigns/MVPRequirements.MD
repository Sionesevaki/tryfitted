MVP tech stack = NO retailer integration

What the MVP does include:

Chrome desktop extension

User 3D avatar creation (photos → lightweight GLB)

Automatic product-page detection

AI-assisted product data extraction from the page itself

Measurement-based fit analysis

3D fit visualization (proxy garment)

Size recommendation + confidence

GPU worker on RunPod for avatar generation

Core API + caching on Coolify

All of this works without any retailer script, SDK, or setup.

❌ What is NOT in the MVP (explicitly excluded)

❌ Retailer dashboard

❌ Retailer JavaScript widget / script

❌ Retailer API keys

❌ Retailer-provided garment measurements

❌ Retailer analytics / reporting

❌ Retailer onboarding flow

When retailer integration was mentioned earlier, that was future-phase context, not part of the MVP build.

Where retailer integration lives (future, not MVP)

If/when you add it later, it would be:

A new backend module (/retailers)

A simple JS embed for product pages

Optional size-chart / material uploads

Better accuracy & analytics

It does not change:

the extension architecture

the avatar system

the GPU worker

the fit engine