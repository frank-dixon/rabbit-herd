from django import template

from ..program_plan import pairs_text

register = template.Library()


@register.filter
def plan_genes(genes, target):
    """A breeder's genotype at the loci a program's target cares about."""
    return pairs_text(genes or {}, target or {})
