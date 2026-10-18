"""Computed genetics reads (genes design B, specs/genes-rethink.md).

Gene rows hold what a person recorded. A rabbit with genes_implied=True also
has probable genes at every locus its breed, color and eye color prove, read
from gene_fill instead of stored rows. genes_of() is the one read every
genetics view uses: stored rows plus the computed ones. A rabbit that isn't
flagged reads its stored rows only.

Herd pedigrees already come from walking dam and sire up the herd
(pedigree.build_tree, pairings.ancestors); the cleanup only drops stored
ancestor rows that walk gives back unchanged.

Reads are cached per request (see middleware) so a page that asks for the
same rabbit's genes or parents many times does the work once.
"""

import contextvars

_cache = contextvars.ContextVar("rabbits_derived_cache", default=None)


def middleware(get_response):
    """Give each GET/HEAD request its own read cache, dropped when it ends.
    Requests that write (POST and the rest) read uncached."""

    def handle(request):
        token = _cache.set({} if request.method in ("GET", "HEAD") else None)
        try:
            return get_response(request)
        finally:
            _cache.reset(token)

    return handle


def memo(key, compute):
    store = _cache.get()
    if store is None:
        return compute()
    if key not in store:
        store[key] = compute()
    return store[key]


def peek(key):
    """A value memo() already computed this request, else None."""
    store = _cache.get()
    return store.get(key) if store else None


def forget(rabbit_id=None):
    """Drop cached reads after a write in the same request (wired to model signals;
    queryset update() and delete() callers must call it themselves)."""
    store = _cache.get()
    if store:
        store.clear()


def implied_genes(rabbit):
    """Unsaved probable Gene rows for what the coat proves, in locus order."""
    from . import gene_fill
    from .models import Gene

    fill = gene_fill.from_breed_and_color(rabbit.breed or "", rabbit.color or "", rabbit.eye_color or "")
    return [Gene(rabbit_id=rabbit.pk, locus=locus, genotype=fill[locus], certainty=Gene.Certainty.PROBABLE, note="")
            for locus in gene_fill.LOCI if fill.get(locus)]


def _stored(rabbit):
    return list(rabbit.genes.all())  # honors prefetch_related("genes")


def _new(rabbit, stored):
    if not rabbit.genes_implied:
        return stored
    from . import gene_fill

    have = {g.locus for g in stored}
    extra = [g for g in implied_genes(rabbit) if g.locus not in have]
    if not extra:
        return stored
    order = {locus: i for i, locus in enumerate(gene_fill.LOCI)}
    return sorted(stored + extra, key=lambda g: order.get(g.locus, len(order)))


def gene_key(genes):
    return [(g.locus, g.genotype, g.certainty, g.note) for g in genes]


def genes_of(rabbit):
    """A herd rabbit's genes as a list of Gene objects (some may be unsaved)."""
    if rabbit is None:
        return []
    if rabbit.pk is None:
        return _genes_of(rabbit)
    return list(memo(("genes", rabbit.pk, rabbit.genes_implied), lambda: _genes_of(rabbit)))


def _genes_of(rabbit):
    return _new(rabbit, _stored(rabbit))


def has_gene(rabbit, locus):
    return any(g.locus == locus for g in genes_of(rabbit))


def materialize(rabbit):
    """Before a write to a rabbit's genes or coat: store its computed genes as
    rows and clear genes_implied, so edits behave as they always have.
    History is not logged for these rows; nothing the keeper sees changes."""
    from .history import quiet
    from .models import Gene, Rabbit

    if not rabbit or not rabbit.pk:
        return
    flagged = Rabbit.all_objects.filter(pk=rabbit.pk, genes_implied=True).values("breed", "color", "eye_color").first()
    if not flagged:
        return
    snapshot = Rabbit(pk=rabbit.pk, **flagged)
    have = set(Gene.objects.filter(rabbit_id=rabbit.pk).values_list("locus", flat=True))
    with quiet():
        Gene.objects.bulk_create([g for g in implied_genes(snapshot) if g.locus not in have])
        Rabbit.all_objects.filter(pk=rabbit.pk).update(genes_implied=False)
    rabbit.genes_implied = False
    if hasattr(rabbit, "_prefetched_objects_cache"):
        rabbit._prefetched_objects_cache.pop("genes", None)
    forget()


def _coat_changing(sender, instance, raw=False, **kwargs):
    """A flagged rabbit's computed genes follow its coat, so store them before
    the breed, color or eye color changes."""
    if raw or not instance.pk or not instance.genes_implied:
        return
    old = sender._base_manager.filter(pk=instance.pk).values("breed", "color", "eye_color", "genes_implied").first()
    if old and old["genes_implied"] and any(old[f] != getattr(instance, f) for f in ("breed", "color", "eye_color")):
        materialize(instance)


def _changed(sender, **kwargs):
    forget()


def connect():
    from django.db.models.signals import post_delete, post_save, pre_save

    from .models import Gene, PedigreeEntry, Rabbit, Relative

    pre_save.connect(_coat_changing, sender=Rabbit, dispatch_uid="derived-coat-changing")
    for model in (Gene, PedigreeEntry, Relative, Rabbit):
        key = model._meta.label_lower
        post_save.connect(_changed, sender=model, dispatch_uid=f"derived-saved-{key}")
        post_delete.connect(_changed, sender=model, dispatch_uid=f"derived-deleted-{key}")
