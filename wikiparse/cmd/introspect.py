import click


@click.group()
def introspect_group():
    pass


@introspect_group.command()
@click.argument("outf", type=click.Path())
def dump_fst(outf):
    import hfst
    from wikiparse.parse_assoc import get_parse_bit_fst

    parse_bit_fst = get_parse_bit_fst()
    ostr = hfst.HfstOutputStream(filename=outf, type=parse_bit_fst.get_type())
    ostr.write(parse_bit_fst)
    ostr.flush()
    ostr.close()
