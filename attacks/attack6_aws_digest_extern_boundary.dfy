// Attack 6: extern-boundary spec laundering — real-world demonstration.
//
// Source: github.com/aws/aws-cryptographic-material-providers-library
//         AwsCryptographyPrimitives/src/Digest.dfy
//         module Digest, method Digest.
//
// The AWS Dafny postcondition for SHA-2 hashing is reproduced verbatim
// here, modulo the extern-call body. The postcondition constrains only
// the output sequence length:
//
//     ensures res.Success? ==> |res.value| == Length(input.digestAlgorithm) as nat
//
// Cryptographic hash properties (preimage resistance, collision
// resistance, the SHA-2 algorithm definition itself) are not constrained
// at the Dafny level. The AWS implementation calls `ExternDigest.Digest`,
// a method marked `{:extern}` whose body is outside the verifier's
// scope. Security rests on the extern boundary being trusted.
//
// The Dafny postcondition alone admits an implementation that returns
// `Length(alg)` zero bytes. Such an implementation satisfies the
// postcondition exactly; an adversarial replacement of ExternDigest
// with a constant-output stub would propagate undetected by the
// verifier.
//
// This is not a constructed attack. It is the unmodified AWS
// specification applied to a self-contained scaffolding (Result and
// DigestAlgorithm definitions extracted to make the file verify
// without the full AWS module graph). The composed detector's check (c)
// flags this method via the trivial-implementation catalog;
// IronSpec ASC does not flag it because `input.digestAlgorithm` is
// referenced in the postcondition through the `Length` call.

newtype uint8 = x: int | 0 <= x < 256

datatype DigestAlgorithm = SHA_512 | SHA_384 | SHA_256

datatype Result<T> = Success(value: T) | Failure

function Length(algorithm: DigestAlgorithm): nat
{
  match algorithm
  case SHA_512 => 64
  case SHA_384 => 48
  case SHA_256 => 32
}

method DigestLaundered(algorithm: DigestAlgorithm, message: seq<uint8>)
    returns (res: Result<seq<uint8>>)
  ensures res.Success? ==> |res.value| == Length(algorithm)
{
  res := Success(seq(Length(algorithm), _ => 0 as uint8));
}
