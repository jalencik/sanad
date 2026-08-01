<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ArrowRight, FileText, Languages, ScanText, Sparkles } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import TopBar from '@/components/layout/TopBar.vue'

const { t } = useI18n()

const languages = ['Uzbek', 'Russian', 'English', 'Karakalpak', 'Kazakh', 'Tajik']
</script>

<template>
  <div class="px-safe flex min-h-dvh flex-col">
    <TopBar :show-workspace-link="true" />

    <!-- Hero: asymmetric two-column, not a centered badge+H1 -->
    <section class="mx-auto w-full max-w-[1600px] px-4 md:px-6 pb-16 pt-14 md:pt-20">
      <div class="grid gap-12 md:grid-cols-[1.05fr_0.95fr] md:items-center">
        <div>
          <h1 class="font-display max-w-xl text-4xl leading-[1.1] text-foreground md:text-5xl">
            {{ t('landing.heroTitle') }}
          </h1>
          <p class="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground md:text-lg">
            {{ t('landing.heroSubtitle') }}
          </p>
          <div class="mt-8 flex flex-wrap items-center gap-3">
            <Button size="lg" as-child class="h-11 px-5 md:h-9 md:px-2.5">
              <RouterLink to="/app">
                {{ t('landing.ctaOpenWorkspace') }}
                <ArrowRight class="h-4 w-4" />
              </RouterLink>
            </Button>
          </div>
        </div>

        <!-- Live mock of the actual split-screen workspace, built from real design tokens -->
        <div class="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <div class="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <span class="flex h-5 w-5 items-center justify-center rounded bg-primary text-primary-foreground">
              <FileText class="h-3 w-3" />
            </span>
            <span class="font-display text-xs text-foreground">{{ t('landing.mockWorkspaceLabel') }}</span>
          </div>
          <div class="flex h-72">
            <div class="w-[42%] border-r border-border p-3">
              <div class="rounded-md border border-dashed border-border p-3 text-center text-[11px] text-muted-foreground">
                {{ t('landing.mockDropHint') }}
              </div>
              <div class="mt-3 space-y-2">
                <div class="flex items-center gap-2 rounded-md bg-muted p-2">
                  <span class="h-6 w-6 shrink-0 rounded bg-secondary"></span>
                  <div class="min-w-0 flex-1">
                    <div class="h-1.5 w-3/4 rounded bg-foreground/20"></div>
                    <div class="mt-1 h-1.5 w-1/3 rounded bg-success/60"></div>
                  </div>
                </div>
                <div class="flex items-center gap-2 rounded-md p-2">
                  <span class="h-6 w-6 shrink-0 rounded bg-secondary"></span>
                  <div class="min-w-0 flex-1">
                    <div class="h-1.5 w-2/3 rounded bg-foreground/15"></div>
                    <div class="mt-1 h-1.5 w-1/4 rounded bg-warning/50"></div>
                  </div>
                </div>
                <div class="flex items-center gap-2 rounded-md p-2">
                  <span class="h-6 w-6 shrink-0 rounded bg-secondary"></span>
                  <div class="min-w-0 flex-1">
                    <div class="h-1.5 w-4/5 rounded bg-foreground/15"></div>
                    <div class="mt-1 h-1.5 w-1/3 rounded bg-foreground/10"></div>
                  </div>
                </div>
              </div>
            </div>
            <div class="flex flex-1 flex-col">
              <div class="flex-[1.1] space-y-2 border-b border-border p-3">
                <div class="h-2 w-1/2 rounded bg-foreground/25"></div>
                <div class="h-1.5 w-1/3 rounded bg-foreground/10"></div>
                <div class="mt-3 grid grid-cols-2 gap-2">
                  <div class="h-1.5 w-full rounded bg-foreground/10"></div>
                  <div class="h-1.5 w-full rounded bg-foreground/10"></div>
                  <div class="h-1.5 w-2/3 rounded bg-foreground/10"></div>
                  <div class="h-1.5 w-2/3 rounded bg-foreground/10"></div>
                </div>
              </div>
              <div class="flex-1 space-y-2 p-3">
                <div class="flex items-center gap-1.5">
                  <Sparkles class="h-3 w-3 text-accent" />
                  <div class="h-1.5 w-1/4 rounded bg-foreground/20"></div>
                </div>
                <div class="h-1.5 w-full rounded bg-foreground/10"></div>
                <div class="h-1.5 w-5/6 rounded bg-foreground/10"></div>
                <div class="h-1.5 w-3/4 rounded bg-foreground/10"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Pipeline: three unevenly-weighted stages, deliberately not identical icon cards -->
    <section class="border-t border-border bg-muted/40">
      <div class="mx-auto grid max-w-[1600px] gap-8 px-4 md:px-6 py-16 md:grid-cols-12">
        <div class="md:col-span-4">
          <ScanText class="h-5 w-5 text-primary" />
          <h2 class="font-display mt-3 text-xl text-foreground">{{ t('landing.pipeline.readTitle') }}</h2>
          <p class="mt-2 text-sm leading-relaxed text-muted-foreground">
            {{ t('landing.pipeline.readBody') }}
          </p>
        </div>
        <div class="md:col-span-4 md:mt-10">
          <h2 class="font-display text-xl text-foreground">{{ t('landing.pipeline.extractTitle') }}</h2>
          <p class="mt-2 text-sm leading-relaxed text-muted-foreground">
            {{ t('landing.pipeline.extractBody') }}
          </p>
          <div class="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <span class="h-1.5 w-1.5 rounded-full bg-success"></span>
            {{ t('landing.pipeline.extractConfidence') }}
          </div>
        </div>
        <div class="md:col-span-4 md:mt-20">
          <Sparkles class="h-5 w-5 text-accent" />
          <h2 class="font-display mt-3 text-xl text-foreground">{{ t('landing.pipeline.explainTitle') }}</h2>
          <p class="mt-2 text-sm leading-relaxed text-muted-foreground">
            {{ t('landing.pipeline.explainBody') }}
          </p>
        </div>
      </div>
    </section>

    <!-- Languages -->
    <section class="mx-auto w-full max-w-[1600px] px-4 md:px-6 py-16">
      <div class="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div class="flex items-center gap-3">
          <Languages class="h-5 w-5 text-muted-foreground" />
          <h2 class="font-display text-xl text-foreground">{{ t('landing.languagesTitle') }}</h2>
        </div>
        <ul class="flex flex-wrap gap-2">
          <li
            v-for="lang in languages"
            :key="lang"
            class="rounded-full border border-border px-3 py-1 text-xs text-foreground"
          >
            {{ lang }}
          </li>
        </ul>
      </div>
    </section>

    <!-- Closing CTA -->
    <section class="border-t border-border">
      <div class="mx-auto flex max-w-[1600px] flex-col items-start gap-4 px-4 md:px-6 py-16 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 class="font-display text-2xl text-foreground">{{ t('landing.closingTitle') }}</h2>
          <p class="mt-1 text-sm text-muted-foreground">{{ t('landing.closingSubtitle') }}</p>
        </div>
        <Button size="lg" as-child class="h-11 px-5 md:h-9 md:px-2.5">
          <RouterLink to="/app">
            {{ t('landing.ctaOpenWorkspace') }}
            <ArrowRight class="h-4 w-4" />
          </RouterLink>
        </Button>
      </div>
    </section>

    <footer class="border-t border-border">
      <div class="pb-safe mx-auto flex max-w-[1600px] flex-col gap-2 px-4 py-8 text-xs text-muted-foreground md:flex-row md:items-center md:justify-between md:px-6">
        <span>{{ t('landing.footerTagline') }}</span>
        <span>{{ t('landing.footerStack') }}</span>
      </div>
    </footer>
  </div>
</template>
