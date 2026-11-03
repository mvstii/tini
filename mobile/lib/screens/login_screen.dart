import 'package:flutter/material.dart';

import '../api.dart';
import '../widgets/brand.dart';
import '../widgets/studio.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.api, required this.onDone});
  final Api api;
  final VoidCallback onDone;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _register = false;
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final email = _email.text.trim();
      await (_register
          ? widget.api.register(email, _password.text)
          : widget.api.login(email, _password.text));
      widget.onDone();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Sunucuya ulaşılamadı');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: AmbientBackground(
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 400),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const StaggerIn(index: 0, child: BrandHeader()),
                    const SizedBox(height: 32),
                    StaggerIn(
                      index: 2,
                      child: StudioSurface(
                        padding: const EdgeInsets.fromLTRB(18, 10, 18, 18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            TextField(
                              controller: _email,
                              keyboardType: TextInputType.emailAddress,
                              autofillHints: const [AutofillHints.email],
                              decoration: const InputDecoration(
                                  labelText: 'E-posta', prefixIcon: Icon(Icons.mail_outline)),
                            ),
                            TextField(
                              controller: _password,
                              obscureText: true,
                              autofillHints: const [AutofillHints.password],
                              decoration: const InputDecoration(
                                  labelText: 'Parola', prefixIcon: Icon(Icons.lock_outline)),
                            ),
                            AnimatedSize(
                              duration: const Duration(milliseconds: 200),
                              child: _error == null
                                  ? const SizedBox(width: double.infinity)
                                  : Padding(
                                      padding: const EdgeInsets.only(top: 12),
                                      child: Text(_error!,
                                          style: TextStyle(color: theme.colorScheme.error)),
                                    ),
                            ),
                            const SizedBox(height: 18),
                            StudioButton(
                              label: _register ? 'Hesap oluştur' : 'Giriş yap',
                              icon: _register ? Icons.person_add_alt_1_rounded : Icons.login_rounded,
                              busy: _busy,
                              onPressed: _busy ? null : _submit,
                            ),
                          ],
                        ),
                      ),
                    ),
                    StaggerIn(
                      index: 3,
                      child: TextButton(
                        onPressed: _busy ? null : () => setState(() => _register = !_register),
                        child: Text(_register ? 'Zaten hesabım var' : 'Yeni hesap oluştur'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
